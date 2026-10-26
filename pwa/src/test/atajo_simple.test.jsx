// «Registro automático al pagar con el iPhone»: un solo flujo de 3 pasos, uno por pantalla,
// con verificación en vivo y lo avanzado plegado.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  apiKey: vi.fn(),
  regenerarApiKey: vi.fn(),
  pagoDePrueba: vi.fn(),
  movimientosPorConfirmar: vi.fn(),
  conexionesEstado: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))

import { DialogosProvider } from '../lib/DialogosContext'
import ConectarDispositivo, { ATAJO_CIERRE_URL, ATAJO_ICLOUD_URL } from '../screens/ConectarDispositivo'
import { explicarErrorPrueba, leerPaso, CLAVE_PASO } from '../lib/atajoPrueba'

const UA_IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148'
const UA_ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile'
const uaOriginal = window.navigator.userAgent
const poner = (ua) => Object.defineProperty(window.navigator, 'userAgent', { value: ua, configurable: true })

const montar = () =>
  render(
    <DialogosProvider>
      <MemoryRouter>
        <ConectarDispositivo />
      </MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  localStorage.clear()
  poner(UA_IPHONE)
  api.apiKey.mockResolvedValue({ api_key: 'cdm_clave_larga', nueva: true, tiene_clave: true })
  api.conexionesEstado.mockResolvedValue({ atajo: { ultimo_uso: null } })
})
afterEach(() => poner(uaOriginal))

describe('Intro', () => {
  it('se llama «Registro automático», explica en 2 frases y dice que funciona en iPhone', async () => {
    montar()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Registro automático de tus pagos')
    expect(screen.getByText(/Cada vez que pagas con Apple Pay, CuadraMe lo anota solo/)).toBeInTheDocument()
    expect(screen.getByText('Funciona en iPhone')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Empezar/ })).toBeInTheDocument()
    expect(screen.queryByText(/endpoint|header|token/i)).toBeNull()
  })

  it('explica qué es un atajo y una automatización, con el dibujo de cómo funciona', () => {
    montar()
    const caja = screen.getByTestId('como-funciona')
    expect(within(caja).getByRole('img', { name: /pagas con tu celular/ })).toBeInTheDocument()
    expect(caja).toHaveTextContent(/Atajo:/)
    expect(caja).toHaveTextContent(/Automatización:/)
  })

  it('en Android muestra el flujo de la app CuadraMe Captura, con 5 pasos y dibujos', () => {
    poner(UA_ANDROID)
    montar()
    const flujo = screen.getByTestId('android-captura')
    const pasos = within(flujo).getByRole('list', { name: 'Pasos para Android' })
    expect(within(pasos).getAllByRole('listitem')).toHaveLength(5)
    expect(within(pasos).getAllByRole('img').length).toBeGreaterThanOrEqual(5)
    expect(screen.getByTestId('plataforma-android')).toHaveAttribute('aria-pressed', 'true')
  })

  it('se puede cambiar a iPhone desde Android, y los pasos de Atajos aparecen', async () => {
    poner(UA_ANDROID)
    montar()
    await userEvent.click(screen.getByTestId('plataforma-ios'))
    expect(screen.queryByTestId('android-captura')).toBeNull()
    expect(screen.getByRole('button', { name: /Empezar/ })).toBeInTheDocument()
  })

  it('en un computador (ni iPhone ni Android) ofrece traer los movimientos por correo o extracto', () => {
    poner('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36')
    montar()
    const link = within(screen.getByTestId('otro-dispositivo')).getByText(/correo o extracto/)
    expect(link.closest('a')).toHaveAttribute('href', '/sincronizacion')
  })
})

describe('Flujo en pasos', () => {
  it('muestra un paso por pantalla con indicador, y se puede volver atrás', async () => {
    montar()
    await userEvent.click(screen.getByRole('button', { name: /Empezar/ }))

    expect(screen.getByText('Paso 1 de 3')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Copia tu clave' })).toBeInTheDocument()
    expect(screen.getByText(/tu llave para que el atajo te reconozca/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Instala el atajo' })).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: /Siguiente/ }))
    expect(screen.getByText('Paso 2 de 3')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Instalar el atajo/ })).toHaveAttribute('href', ATAJO_ICLOUD_URL)
    expect(screen.getByText(/pega la clave/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Siguiente/ }))
    expect(screen.getByText('Paso 3 de 3')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Actívalo en Wallet' })).toBeInTheDocument()
    const lista = screen.getByTestId('pasos-wallet')
    expect(within(lista).getAllByRole('listitem')).toHaveLength(4)
    expect(within(lista).getByText('Transacción')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Atrás' }))
    expect(screen.getByText('Paso 2 de 3')).toBeInTheDocument()
  })

  it('copia la clave con un botón grande y lo confirma', async () => {
    montar()
    await userEvent.click(screen.getByRole('button', { name: /Empezar/ }))
    const boton = await screen.findByRole('button', { name: 'Copiar clave' })
    expect(boton).toHaveTextContent('Copiar mi clave')
    await userEvent.click(boton)
    expect(await navigator.clipboard.readText()).toBe('cdm_clave_larga')
    expect(await screen.findByText(/ya la tienes copiada/)).toBeInTheDocument()
  })

  it('recuerda en qué paso quedó y lo retoma', async () => {
    const a = montar()
    await userEvent.click(screen.getByRole('button', { name: /Empezar/ }))
    await userEvent.click(screen.getByRole('button', { name: /Siguiente/ }))
    expect(leerPaso()).toBe(1)
    a.unmount()
    montar()
    expect(screen.getByText('Paso 2 de 3')).toBeInTheDocument()
    expect(localStorage.getItem(CLAVE_PASO)).toBe('1')
  })

  it('el segundo atajo (cierre de app) es opcional y está plegado dentro del paso 3', async () => {
    localStorage.setItem(CLAVE_PASO, '2')
    montar()
    const opcional = screen.getByTestId('opcional-efectivo')
    expect(opcional.tagName).toBe('DETAILS')
    expect(opcional).not.toHaveAttribute('open')
    expect(opcional).toHaveTextContent(/Para registrar pagos en efectivo o en cuentas sin Apple Pay/)
    expect(within(opcional).getByRole('link', { hidden: true, name: /atajo de efectivo/ })).toHaveAttribute('href', ATAJO_CIERRE_URL)
  })

  it('todo lo avanzado queda plegado bajo «Avanzado»', async () => {
    montar()
    const avanzado = screen.getByTestId('avanzado')
    expect(avanzado).not.toHaveAttribute('open')
    expect(avanzado).not.toHaveTextContent('Armar el atajo a mano')
    await userEvent.click(within(avanzado).getByText('Avanzado'))
    expect(await within(avanzado).findByText(/Armar el atajo a mano/)).toBeInTheDocument()
    expect(avanzado).toHaveTextContent('Android')
  })
})

describe('Verificación en vivo', () => {
  beforeEach(() => localStorage.setItem(CLAVE_PASO, '3'))

  it('«Probar ahora» usa la sesión, llega a por-confirmar y explica qué falta del iPhone', async () => {
    api.pagoDePrueba.mockResolvedValue({ id: 'p1', mensaje: 'ok' })
    api.movimientosPorConfirmar.mockResolvedValue([{ id: 'p1' }])
    montar()
    await userEvent.click(await screen.findByRole('button', { name: 'Probar ahora' }))
    expect(await screen.findByText('La prueba llegó a CuadraMe')).toBeInTheDocument()
    expect(api.pagoDePrueba).toHaveBeenCalledWith(null)
    expect(screen.getByText(/clave quedó mal pegada/)).toBeInTheDocument()
    expect(screen.getByText(/atajo no está instalado/)).toBeInTheDocument()
  })

  it('sin cuenta: lo explica en simple y manda a crear una', async () => {
    const e = new Error('x')
    e.status = 404
    api.pagoDePrueba.mockRejectedValue(e)
    montar()
    await userEvent.click(await screen.findByRole('button', { name: 'Probar ahora' }))
    const alerta = await screen.findByTestId('prueba-error')
    expect(alerta).toHaveTextContent(/Nu, Nequi/)
    expect(within(alerta).getByRole('link', { name: 'Crear una cuenta' })).toHaveAttribute('href', '/cuentas')
  })

  it('si el atajo real ya envió algo, el paso se marca solo (sin que lo marquen a mano)', async () => {
    api.conexionesEstado.mockResolvedValue({ atajo: { ultimo_uso: '2026-10-09T15:00:00' } })
    montar()
    expect(await screen.findByTestId('listo')).toHaveTextContent('Tu registro automático funciona')
    expect(screen.queryByRole('button', { name: 'Probar ahora' })).toBeNull()
  })

  it('si el atajo llega mientras miras la pantalla, celebra el primer pago', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    api.conexionesEstado
      .mockResolvedValueOnce({ atajo: { ultimo_uso: null } })
      .mockResolvedValue({ atajo: { ultimo_uso: '2026-10-09T15:00:00' } })
    montar()
    await screen.findByRole('button', { name: 'Probar ahora' })
    await vi.advanceTimersByTimeAsync(6500)
    expect(await screen.findByTestId('listo')).toHaveTextContent('Tu primer pago de prueba llegó')
    vi.useRealTimers()
  })
})

describe('explicarErrorPrueba', () => {
  it('traduce cada fallo a lenguaje simple con un siguiente paso', () => {
    expect(explicarErrorPrueba({ status: 401 }).titulo).toMatch(/sesión/)
    expect(explicarErrorPrueba({ status: 429 }).texto).toMatch(/Espera/)
    expect(explicarErrorPrueba(new Error('Failed to fetch')).titulo).toMatch(/Sin conexión/)
    expect(explicarErrorPrueba({ codigo: 'no-llego' }).texto).toMatch(/otra vez/)
  })
})

describe('sin jerga en la pantalla principal', () => {
  it('no aparecen endpoint, header ni token fuera de «Avanzado»', async () => {
    montar()
    await userEvent.click(screen.getByRole('button', { name: /Empezar/ }))
    const visible = document.body.cloneNode(true)
    visible.querySelector('[data-testid="avanzado"]')?.remove()
    expect(visible.textContent).not.toMatch(/endpoint|header|token|automatización de Atajos/i)
    await waitFor(() => expect(api.apiKey).toHaveBeenCalled())
  })
})
