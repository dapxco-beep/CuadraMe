import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
const auth = vi.hoisted(() => ({ usuario: { id: 'u-ma', email: 'a@test.com', nombre: 'Ana' } }))
const iniciar = vi.hoisted(() => vi.fn())
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ iconoDe: () => '💳' }) }))
vi.mock('../lib/autoarreglo', async (orig) => ({ ...(await orig()), iniciar }))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import Perfil from '../screens/Perfil'
import PrevioImportacion from '../components/PrevioImportacion'
import { esMismoGastoSeguro } from '../lib/modoAutomatico'
import { lineasConteo, textoAviso } from '../lib/autoarreglo'

const dudoso = (k, monto, registrado, extra = {}) => ({
  k, fp: k, estado: 'dudoso', descripcion: 'COMPRA TIENDA', fecha: '2026-10-10', monto, matchId: `m-${k}`,
  registrado: { descripcion: 'Tienda', monto: registrado, fecha: '2026-10-11' }, ...extra,
})

describe('esMismoGastoSeguro (regla pura)', () => {
  it('monto idéntico, ≤3 días y 1:1 -> se junta solo', () => {
    const it = dudoso('a', 30000, 30000)
    expect(esMismoGastoSeguro(it, [it])).toBe(true)
    const centavos = dudoso('b', 30000.4, 30000)
    expect(esMismoGastoSeguro(centavos, [centavos])).toBe(true)
  })
  it('NEGATIVO: monto distinto, más de 3 días, lectura dudosa o dos líneas para el mismo movimiento -> se pregunta', () => {
    const distinto = dudoso('a', 30500, 30000)
    expect(esMismoGastoSeguro(distinto, [distinto])).toBe(false)
    const lejos = dudoso('b', 30000, 30000, { fecha: '2026-10-01' })
    expect(esMismoGastoSeguro(lejos, [lejos])).toBe(false)
    const lectura = dudoso('c', 30000, 30000, { dudosa: true })
    expect(esMismoGastoSeguro(lectura, [lectura])).toBe(false)
    const x = dudoso('d', 30000, 30000, { matchId: 'm-comun' })
    const y = dudoso('e', 30000, 30000, { matchId: 'm-comun' })
    expect(esMismoGastoSeguro(x, [x, y])).toBe(false)
    const rechazado = dudoso('f', 30000, 30000, { noAuto: true })
    expect(esMismoGastoSeguro(rechazado, [rechazado])).toBe(false)
  })
})

describe('PrevioImportacion con Modo automático', () => {
  beforeEach(() => iniciar.mockReset())

  it('junta solo lo seguro y pregunta solo lo que difiere en el monto', async () => {
    const onDecidir = vi.fn().mockResolvedValue()
    const seguro = dudoso('a', 30000, 30000)
    const distinto = dudoso('b', 12000, 11000, { matchId: 'm-b' })
    render(<PrevioImportacion items={[seguro, distinto]} automatico onDecidir={onDecidir} onDeshacerAuto={vi.fn()} />)
    await waitFor(() => expect(onDecidir).toHaveBeenCalledWith([seguro], 'mismo', true))
    expect(screen.getByTestId('dudosa-b')).toBeInTheDocument()
    expect(screen.queryByTestId('dudosa-a')).not.toBeInTheDocument()
  })

  it('con el modo apagado pregunta todo, como antes', () => {
    const onDecidir = vi.fn()
    const seguro = dudoso('a', 30000, 30000)
    render(<PrevioImportacion items={[seguro]} automatico={false} onDecidir={onDecidir} />)
    expect(screen.getByTestId('dudosa-a')).toBeInTheDocument()
    expect(onDecidir).not.toHaveBeenCalled()
  })

  it('lo ya unido muestra la línea clara y Deshacer lo devuelve a pregunta', async () => {
    const onDeshacerAuto = vi.fn()
    const unida = dudoso('a', 30000, 30000, { estado: 'ya', autoUnida: true })
    render(<PrevioImportacion items={[unida]} automatico onDecidir={vi.fn()} onDeshacerAuto={onDeshacerAuto} />)
    expect(screen.getByTestId('previo-unidas')).toHaveTextContent('Junté 1 línea que era el mismo gasto')
    await userEvent.click(screen.getByTestId('previo-deshacer-union'))
    expect(onDeshacerAuto).toHaveBeenCalledWith([unida])
  })

  it('con el extracto ya en el servidor pide al autoarreglo juntar (con su Deshacer) en vez de decidir aquí', async () => {
    const onDecidir = vi.fn()
    render(<PrevioImportacion items={[dudoso('a', 30000, 30000)]} automatico servidor onDecidir={onDecidir} />)
    await waitFor(() => expect(iniciar).toHaveBeenCalledWith({ forzar: true }))
    expect(onDecidir).not.toHaveBeenCalled()
    expect(screen.getByTestId('previo-unidas')).toHaveTextContent('la junto yo')
  })
})

describe('textos del aviso', () => {
  it('solo cosas del modo automático: línea directa', () => {
    const r = { texto: 'Listo, ordené tus cuentas: registré 3 movimientos de tus correos.', contadores: { correos_registrados: 3 } }
    expect(textoAviso(r)).toBe('Registré 3 movimientos de tus correos.')
    expect(lineasConteo(r.contadores)).toEqual(['Registré 3 movimientos de tus correos'])
  })
  it('mezclado con el orden de siempre mantiene el encabezado', () => {
    const r = { texto: 'Listo, ordené tus cuentas: corregí 2 compras, registré 1 movimiento de tus correos.', contadores: { compras_corregidas: 2, correos_registrados: 1 } }
    expect(textoAviso(r)).toMatch(/^Ordené tus cuentas:/)
  })
})

describe('Perfil: Modo automático', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    Object.assign(api, {
      apiKey: vi.fn().mockResolvedValue({ api_key: 'k' }),
      confianzaAutoimport: vi.fn().mockResolvedValue({ confianza_autoimport: 0.8, activo: false }),
      modoAutomatico: vi.fn().mockResolvedValue({ activo: true }),
      guardarModoAutomatico: vi.fn().mockImplementation(async (v) => ({ activo: v })),
    })
  })
  const verPerfil = () => render(<ThemeProvider><DialogosProvider><MemoryRouter><Perfil /></MemoryRouter></DialogosProvider></ThemeProvider>)

  it('viene activado, explica qué hace y se puede apagar y volver a encender', async () => {
    verPerfil()
    const sw = await screen.findByTestId('switch-modo-automatico')
    await waitFor(() => expect(sw).toHaveAttribute('aria-checked', 'true'))
    expect(screen.getByTestId('modo-automatico')).toHaveTextContent('Deshacer')
    await userEvent.click(sw)
    await waitFor(() => expect(sw).toHaveAttribute('aria-checked', 'false'))
    expect(api.guardarModoAutomatico).toHaveBeenLastCalledWith(false)
    await userEvent.click(sw)
    await waitFor(() => expect(sw).toHaveAttribute('aria-checked', 'true'))
    expect(api.guardarModoAutomatico).toHaveBeenLastCalledWith(true)
  })

  it('si no se puede guardar, el interruptor vuelve a como estaba', async () => {
    api.guardarModoAutomatico.mockRejectedValueOnce(new Error('sin red'))
    verPerfil()
    const sw = await screen.findByTestId('switch-modo-automatico')
    await waitFor(() => expect(sw).toHaveAttribute('aria-checked', 'true'))
    await userEvent.click(sw)
    await waitFor(() => expect(sw).toHaveAttribute('aria-checked', 'true'))
  })
})
