// Registro con Apple Wallet: bandeja "¿son tuyos?", pregunta "¿hiciste algún movimiento?"
// y asistente "Conectar tu celular".
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  movimientosPorConfirmar: vi.fn(),
  confirmarCategorias: vi.fn(),
  editarMovimiento: vi.fn(),
  eliminarMovimiento: vi.fn(),
  apiKey: vi.fn(),
  pagoDePrueba: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({
    cuentas: [{ id: 'c1', nombre: 'Visa Bancolombia' }, { id: 'c2', nombre: 'Efectivo' }],
    recargar: vi.fn(),
  }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Transporte', 'Otros'], iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import BandejaPorConfirmar from '../components/BandejaPorConfirmar'
import PreguntaMovimiento from '../components/PreguntaMovimiento'
import {
  CLAVE_BANDEJA,
  CLAVE_PREGUNTA,
  debeMostrarBandeja,
  debePreguntarMovimiento,
  fechaLocalISO,
  marcarBandejaAbierta,
  ocultarPreguntaHoy,
  preguntaOcultaHoy,
  recordarBandejaCerrada,
} from '../lib/bandeja'

const mov = (id, extra = {}) => ({
  id, cuenta_id: 'c1', descripcion: `Comercio ${id}`, categoria: 'Comida', tipo: 'expense',
  monto: 18500, fecha: '2026-10-03T12:30:00', fuente: 'wallet', cat_origen: 'wallet', cat_confirmada: false, ...extra,
})

const montar = (ui) =>
  render(
    <DialogosProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  try { window.localStorage.clear() } catch { /* */ }
  marcarBandejaAbierta(false)
})

describe('lógica de la bandeja', () => {
  it('no se muestra sin pendientes', () => {
    expect(debeMostrarBandeja([], null)).toBe(false)
  })

  it('se muestra la primera vez y no vuelve en la hora siguiente si no hay nuevos', () => {
    const lista = [mov('a'), mov('b')]
    expect(debeMostrarBandeja(lista, null)).toBe(true)
    const ahora = 1_000_000_000
    const estado = { ts: ahora, ids: ['a', 'b'] }
    expect(debeMostrarBandeja(lista, estado, ahora + 10 * 60 * 1000)).toBe(false)
    expect(debeMostrarBandeja(lista, estado, ahora + 61 * 60 * 1000)).toBe(true)
  })

  it('vuelve a salir antes de la hora si llegó un movimiento nuevo', () => {
    const ahora = 1_000_000_000
    const estado = { ts: ahora, ids: ['a'] }
    expect(debeMostrarBandeja([mov('a'), mov('nuevo')], estado, ahora + 60 * 1000)).toBe(true)
  })

  it('recordarBandejaCerrada guarda ids y hora, y tolera un localStorage que falla', () => {
    recordarBandejaCerrada([mov('a')], 5)
    expect(JSON.parse(window.localStorage.getItem(CLAVE_BANDEJA))).toEqual({ ts: 5, ids: ['a'] })
    const espia = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('bloqueado') })
    expect(() => recordarBandejaCerrada([mov('a')])).not.toThrow()
    espia.mockRestore()
  })
})

describe('Bandeja "¿son tuyos?"', () => {
  it('muestra "Detectamos N movimientos" con una tarjeta por movimiento', async () => {
    api.movimientosPorConfirmar.mockResolvedValue([mov('a'), mov('b')])
    montar(<BandejaPorConfirmar />)
    expect(await screen.findByText(/Detectamos 2 movimientos: ¿son tuyos\?/)).toBeInTheDocument()
    expect(screen.getAllByTestId('tarjeta-por-confirmar')).toHaveLength(2)
    expect(screen.getByText('Comercio a')).toBeInTheDocument()
  })

  it('no sale si no hay pendientes', async () => {
    api.movimientosPorConfirmar.mockResolvedValue([])
    montar(<BandejaPorConfirmar />)
    await waitFor(() => expect(api.movimientosPorConfirmar).toHaveBeenCalled())
    expect(screen.queryByTestId('bandeja-por-confirmar')).toBeNull()
  })

  it('confirma uno con "Es mío" y lo quita de la lista', async () => {
    api.movimientosPorConfirmar.mockResolvedValue([mov('a'), mov('b')])
    api.confirmarCategorias.mockResolvedValue({ ok: true })
    montar(<BandejaPorConfirmar />)
    const tarjeta = (await screen.findAllByTestId('tarjeta-por-confirmar'))[0]
    await userEvent.click(within(tarjeta).getByRole('button', { name: /Es mío/ }))
    await waitFor(() => expect(api.confirmarCategorias).toHaveBeenCalledWith(['a']))
    await waitFor(() => expect(screen.getAllByTestId('tarjeta-por-confirmar')).toHaveLength(1))
    expect(screen.getByText(/Detectamos 1 movimiento: /)).toBeInTheDocument()
  })

  it('confirma todos en lote', async () => {
    api.movimientosPorConfirmar.mockResolvedValue([mov('a'), mov('b'), mov('c')])
    api.confirmarCategorias.mockResolvedValue({ ok: true })
    montar(<BandejaPorConfirmar />)
    await userEvent.click(await screen.findByRole('button', { name: /Confirmar todos \(3\)/ }))
    await waitFor(() => expect(api.confirmarCategorias).toHaveBeenCalledWith(['a', 'b', 'c']))
    await waitFor(() => expect(screen.queryByTestId('bandeja-por-confirmar')).toBeNull())
  })

  it('edita monto y categoría y guarda', async () => {
    api.movimientosPorConfirmar.mockResolvedValue([mov('a')])
    api.editarMovimiento.mockResolvedValue({})
    montar(<BandejaPorConfirmar />)
    await userEvent.click(await screen.findByRole('button', { name: /Editar/ }))
    const monto = screen.getByLabelText('Monto')
    await userEvent.clear(monto)
    await userEvent.type(monto, '20000')
    await userEvent.selectOptions(screen.getByLabelText('Categoría'), 'Transporte')
    await userEvent.click(screen.getByRole('button', { name: /Guardar y confirmar/ }))
    await waitFor(() =>
      expect(api.editarMovimiento).toHaveBeenCalledWith('a', { monto: 20000, categoria: 'Transporte', cuenta_id: 'c1' })
    )
  })

  it('descarta con confirmación y llama a eliminar (que revierte el saldo)', async () => {
    api.movimientosPorConfirmar.mockResolvedValue([mov('a')])
    api.eliminarMovimiento.mockResolvedValue({ ok: true })
    montar(<BandejaPorConfirmar />)
    await userEvent.click(await screen.findByRole('button', { name: /No es mío/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Descartar' }))
    await waitFor(() => expect(api.eliminarMovimiento).toHaveBeenCalledWith('a'))
  })

  it('cerrada no vuelve a salir al volver a primer plano, salvo que haya nuevos', async () => {
    api.movimientosPorConfirmar.mockResolvedValue([mov('a')])
    montar(<BandejaPorConfirmar />)
    await userEvent.click(await screen.findByRole('button', { name: 'Ahora no' }))
    expect(screen.queryByTestId('bandeja-por-confirmar')).toBeNull()

    document.dispatchEvent(new Event('visibilitychange'))
    await waitFor(() => expect(api.movimientosPorConfirmar).toHaveBeenCalledTimes(2))
    expect(screen.queryByTestId('bandeja-por-confirmar')).toBeNull()

    api.movimientosPorConfirmar.mockResolvedValue([mov('a'), mov('nuevo')])
    document.dispatchEvent(new Event('visibilitychange'))
    expect(await screen.findByText(/Detectamos 2 movimientos/)).toBeInTheDocument()
  })
})

describe('Pregunta "¿hiciste algún movimiento?"', () => {
  const hoy10am = new Date(2026, 9, 3, 10, 0)
  const hoy3pm = new Date(2026, 9, 3, 15, 0)

  it('pregunta si hoy no hay movimientos, pero no de madrugada', () => {
    expect(debePreguntarMovimiento({ ultimaFecha: '2026-10-02T21:00:00', ahora: hoy10am })).toBe(true)
    expect(debePreguntarMovimiento({ ultimaFecha: null, ahora: hoy10am })).toBe(true)
    expect(debePreguntarMovimiento({ ultimaFecha: '2026-10-02T21:00:00', ahora: new Date(2026, 9, 3, 7, 0) })).toBe(false)
  })

  it('pregunta si pasaron más de 6 horas desde el último de hoy', () => {
    expect(debePreguntarMovimiento({ ultimaFecha: '2026-10-03T09:30:00', ahora: hoy3pm })).toBe(false)
    expect(debePreguntarMovimiento({ ultimaFecha: '2026-10-03T09:00:00', ahora: new Date(2026, 9, 3, 16, 0) })).toBe(true)
  })

  it('"No hice ninguno" la oculta hasta mañana (persistido)', () => {
    expect(preguntaOcultaHoy(hoy10am)).toBe(false)
    ocultarPreguntaHoy(hoy10am)
    expect(window.localStorage.getItem(CLAVE_PREGUNTA)).toBe(JSON.stringify(fechaLocalISO(hoy10am)))
    expect(preguntaOcultaHoy(hoy3pm)).toBe(true)
    expect(preguntaOcultaHoy(new Date(2026, 9, 4, 10, 0))).toBe(false)
  })

  it('ocultar no revienta si localStorage falla', () => {
    const espia = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('bloqueado') })
    expect(() => ocultarPreguntaHoy()).not.toThrow()
    espia.mockRestore()
  })

  it('el componente muestra los dos botones y "No hice ninguno" lo esconde', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(hoy3pm)
    montar(<PreguntaMovimiento ultimaFecha="2026-10-02T20:00:00" />)
    expect(screen.getByText('¿Hiciste algún movimiento?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Registrar gasto/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'No hice ninguno' }))
    expect(screen.queryByTestId('pregunta-movimiento')).toBeNull()
    vi.useRealTimers()
  })

  it('espera mientras la bandeja está abierta', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(hoy3pm)
    marcarBandejaAbierta(true)
    montar(<PreguntaMovimiento ultimaFecha={null} />)
    expect(screen.queryByTestId('pregunta-movimiento')).toBeNull()
    vi.useRealTimers()
  })
})
