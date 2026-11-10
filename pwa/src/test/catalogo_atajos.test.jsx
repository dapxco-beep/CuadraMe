// Guía de atajos en «Registro automático»: la persona elige qué conectar y ve solo sus pasos en tres etapas (Instalar, Activar, Probar).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  apiKey: vi.fn(),
  regenerarApiKey: vi.fn(),
  conexionesEstado: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
const capturas = vi.hoisted(() => ({ CAPTURAS_REALES: {} }))
vi.mock('../lib/capturasGuia', () => capturas)

import { DialogosProvider } from '../lib/DialogosContext'
import CatalogoAtajos, { ATAJOS } from '../components/CatalogoAtajos'
import ConectarDispositivo from '../screens/ConectarDispositivo'
import {
  ATAJO_ICLOUD_URL, ATAJO_NOTIFICACIONES_URL, ATAJO_REGISTRAR_URL, ATAJOS_ACTUALIZADOS,
} from '../lib/atajosEnlaces'

const CLAVE = { clave: 'cdm_demo', cargando: false, tieneClave: true, prefijo: '', recienCreada: false, crearNueva: vi.fn() }

const montarCatalogo = () =>
  render(
    <DialogosProvider>
      <MemoryRouter>
        <CatalogoAtajos claveAtajo={CLAVE} />
      </MemoryRouter>
    </DialogosProvider>
  )

const elegir = (nombre) => userEvent.click(screen.getByRole('button', { name: new RegExp(nombre) }))

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  capturas.CAPTURAS_REALES = {}
  localStorage.clear()
})

describe('Guía de atajos', () => {
  it('sin elegir nada muestra las 3 opciones y pide elegir; la clave se copia en el mismo lugar', () => {
    montarCatalogo()
    const opciones = screen.getByTestId('cual-instalo')
    expect(ATAJOS.map((a) => a.id)).toEqual(['apple-pay', 'notificaciones', 'registrar'])
    expect(opciones).toHaveTextContent('Pagos con Apple Pay')
    expect(opciones).toHaveTextContent('Mi banco me avisa')
    expect(opciones).toHaveTextContent('Mi banco no avisa al enviar')
    expect(screen.getByTestId('elige-una-opcion')).toBeInTheDocument()
    expect(screen.queryByTestId('atajo-registrar')).toBeNull()
    expect(screen.getByTestId('clave-catalogo')).toHaveTextContent('cdm_demo')
    expect(screen.getByRole('button', { name: 'Copiar clave' })).toBeInTheDocument()
  })

  it('al elegir, muestra SOLO ese atajo, con su botón Instalar al enlace correcto', async () => {
    montarCatalogo()
    const esperados = { 'apple-pay': ATAJO_ICLOUD_URL, notificaciones: ATAJO_NOTIFICACIONES_URL, registrar: ATAJO_REGISTRAR_URL }
    for (const a of ATAJOS) {
      await elegir(a.opcion.split(' (')[0])
      const tarjeta = screen.getByTestId(`atajo-${a.id}`)
      const boton = within(tarjeta).getByRole('link', { name: /^Instalar CuadraMe/ })
      expect(boton).toHaveAttribute('href', esperados[a.id])
      expect(boton).toHaveAttribute('target', '_blank')
      expect(boton).toHaveAttribute('rel', expect.stringContaining('noopener'))
      expect(screen.getAllByRole('article')).toHaveLength(1) // solo la guía elegida
      expect(tarjeta).toHaveTextContent(`Para ti si: ${a.paraQuien}`)
    }
  })

  it('cada guía trae tres etapas (Instalar, Activar, Probar) con sus pasos numerados', async () => {
    montarCatalogo()
    for (const a of ATAJOS) {
      await elegir(a.opcion.split(' (')[0])
      const guia = screen.getByTestId(`atajo-${a.id}`)
      for (const fase of ['instalar', 'activar', 'probar']) expect(within(guia).getByTestId(`fase-${fase}`)).toBeInTheDocument()
      expect(within(screen.getByTestId(`pasos-${a.id}`)).getAllByRole('listitem').length).toBeGreaterThanOrEqual(5)
      expect(within(guia).getByTestId('fase-instalar')).toHaveTextContent('pida tu clave, pégala')
    }
    await elegir('Mi banco no avisa')
    expect(screen.getByTestId('pasos-registrar')).toHaveTextContent('Tocar atrás')
    await elegir('Mi banco me avisa')
    expect(screen.getByTestId('pasos-notificaciones')).toHaveTextContent('Cuando recibo una notificación')
    await elegir('Pagos con Apple Pay')
    expect(screen.getByTestId('pasos-apple-pay')).toHaveTextContent('Transacción')
  })

  it('resalta en negrita los textos exactos de los botones de iOS', async () => {
    montarCatalogo()
    await elegir('Mi banco no avisa')
    const negritas = [...screen.getByTestId('fase-activar').querySelectorAll('b')].map((b) => b.textContent)
    expect(negritas).toEqual(expect.arrayContaining(['«Tocar atrás»', '«Doble toque»', '«CuadraMe Registrar»']))
  })

  it('recuerda lo que elegiste la próxima vez', async () => {
    const primera = montarCatalogo()
    await elegir('Mi banco no avisa')
    primera.unmount()
    montarCatalogo()
    expect(screen.getByTestId('atajo-registrar')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Mi banco no avisa/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('usa las capturas reales cuando existen y el dibujo propio cuando no', async () => {
    const primera = montarCatalogo()
    await elegir('Mi banco no avisa')
    expect(screen.getByTestId('atajo-registrar').querySelectorAll('img')).toHaveLength(0)
    expect(screen.getByTestId('atajo-registrar').querySelectorAll('svg[role="img"]').length).toBeGreaterThan(0)
    primera.unmount()
    capturas.CAPTURAS_REALES = { registrar: [{ src: '/guia/registrar-1.webp', alt: 'Tocar atrás en Ajustes' }] }
    const { container } = montarCatalogo() // la elección quedó guardada
    const real = container.querySelector('img[src="/guia/registrar-1.webp"]')
    expect(real).not.toBeNull()
    expect(real).toHaveAttribute('alt', 'Tocar atrás en Ajustes')
  })

  it('«Comprobar si llegó» dice que llegó cuando el atajo se conectó hace pocos minutos', async () => {
    api.conexionesEstado.mockResolvedValue({ atajo: { ultimo_uso: new Date(Date.now() - 2 * 60000).toISOString() } })
    montarCatalogo()
    await elegir('Mi banco no avisa')
    await userEvent.click(screen.getByRole('button', { name: 'Comprobar si llegó' }))
    await waitFor(() => expect(screen.getByTestId('comprobar-llegada').querySelector('[data-resultado="llego"]')).not.toBeNull())
    expect(screen.getByTestId('comprobar-llegada')).toHaveTextContent('¡Llegó!')
  })

  it('«Comprobar si llegó» explica qué hacer si no llegó nada reciente o si falla', async () => {
    api.conexionesEstado.mockResolvedValueOnce({ atajo: { ultimo_uso: null } })
    montarCatalogo()
    await elegir('Mi banco me avisa')
    await userEvent.click(screen.getByRole('button', { name: 'Comprobar si llegó' }))
    await waitFor(() => expect(screen.getByTestId('comprobar-llegada').querySelector('[data-resultado="nada"]')).not.toBeNull())
    expect(screen.getByTestId('comprobar-llegada')).toHaveTextContent('Todavía no llega nada')
    api.conexionesEstado.mockResolvedValueOnce({ atajo: { ultimo_uso: new Date(Date.now() - 3 * 3600000).toISOString() } })
    await userEvent.click(screen.getByRole('button', { name: 'Comprobar si llegó' }))
    await waitFor(() => expect(screen.getByTestId('comprobar-llegada')).toHaveTextContent('La última conexión fue'))
    api.conexionesEstado.mockRejectedValueOnce(new Error('sin red'))
    await userEvent.click(screen.getByRole('button', { name: 'Comprobar si llegó' }))
    await waitFor(() => expect(screen.getByTestId('comprobar-llegada').querySelector('[data-resultado="error"]')).not.toBeNull())
  })

  it('en la pestaña «Registro automático» de iPhone la guía aparece desde la primera pantalla', async () => {
    api.apiKey.mockResolvedValue({ api_key: 'cdm_demo', tiene_clave: true, nueva: false })
    api.conexionesEstado.mockResolvedValue({ atajo: { ultimo_uso: null } })
    localStorage.setItem('cuadrame:atajo-paso', '-1')
    render(
      <DialogosProvider>
        <MemoryRouter>
          <ConectarDispositivo />
        </MemoryRouter>
      </DialogosProvider>
    )
    expect(await screen.findByTestId('catalogo-atajos')).toBeInTheDocument()
    expect(screen.getByTestId('cual-instalo')).toHaveTextContent('Mi banco me avisa')
    expect(screen.queryByText(/CuadraMe Cierre/)).toBeNull() // el atajo de cierre de app ya no se ofrece
  })

  it('explica cómo cambiar un atajo anterior y qué revisar si algo falla', () => {
    montarCatalogo()
    const viejo = screen.getByTestId('ya-lo-tenias')
    expect(viejo).toHaveTextContent('iOS no actualiza los atajos solo')
    expect(viejo).toHaveTextContent('Agregar atajo')
    expect(viejo).toHaveTextContent('«2» al final')
    expect(viejo).toHaveTextContent('Automatización')
    const falla = screen.getByTestId('no-funciona')
    for (const tema of ['sin gesto', 'clave no válida', 'automatización no corre', 'Ejecutar inmediatamente', 'Tocar atrás', 'iOS 27', 'No encontré un pago']) {
      expect(falla).toHaveTextContent(tema)
    }
  })

  it('avisa que los atajos se actualizaron, y el aviso se cierra y no vuelve hasta la próxima versión', async () => {
    const primera = montarCatalogo()
    const aviso = screen.getByTestId('aviso-atajos-actualizados')
    expect(aviso).toHaveTextContent(`Actualizamos los atajos (${ATAJOS_ACTUALIZADOS.fecha})`)
    expect(aviso).toHaveTextContent('vuelve a tocar «Instalar»')
    await userEvent.click(within(aviso).getByRole('button', { name: 'Entendido' }))
    expect(screen.queryByTestId('aviso-atajos-actualizados')).toBeNull()
    primera.unmount()
    const segunda = montarCatalogo() // otra visita: ya lo cerró
    expect(screen.queryByTestId('aviso-atajos-actualizados')).toBeNull()
    segunda.unmount()
    localStorage.setItem('cuadrame:atajos-aviso', '2000-01-01') // lo que vio era una versión anterior: con una nueva vuelve a salir
    montarCatalogo()
    expect(screen.getByTestId('aviso-atajos-actualizados')).toBeInTheDocument()
  })
})
