// Punto de partida: «empezar desde hoy» o «recrear mi histórico». Elegir, cambiar, cobertura,
// saldo reconstruido y el aviso de lo anterior que no se muestra.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const CUENTAS = [
  { id: 'c1', nombre: 'Bancolombia Ahorros', saldo: 1500000, icono: 'B', tipo: 'ahorro' },
  { id: 'c2', nombre: 'Efectivo', saldo: 20000, icono: 'E', tipo: 'efectivo' },
]

const api = vi.hoisted(() => ({
  puntoDePartida: vi.fn(),
  guardarPuntoDePartida: vi.fn(),
  coberturaPuntoDePartida: vi.fn(),
  conciliacionPuntoDePartida: vi.fn(),
  ajustarSaldosPuntoDePartida: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
const recargar = vi.hoisted(() => vi.fn())
vi.mock('../lib/CuentasContext', () => ({ useCuentas: () => ({ cuentas: CUENTAS, recargar }) }))

import PuntoDePartida from '../components/PuntoDePartida'
import {
  avisosFaltantes, descripcionPunto, fechaDesdeMeses, fechaLarga, parsearMonto, posponerPuntoDePartida,
  puntoDePartidaPospuesto,
} from '../lib/puntoPartida'

const SIN_ELEGIR = { definido: false, modo: null, fecha: null, saldos: {}, anteriores: { correos: 0, extractos: 0 } }

const montar = (props) =>
  render(
    <MemoryRouter>
      <PuntoDePartida {...props} />
    </MemoryRouter>
  )

beforeEach(() => {
  localStorage.clear()
  Object.values(api).forEach((f) => f.mockReset())
  recargar.mockReset()
  api.puntoDePartida.mockResolvedValue(SIN_ELEGIR)
  api.coberturaPuntoDePartida.mockResolvedValue({ meses: [], cuentas: [] })
  api.conciliacionPuntoDePartida.mockResolvedValue({ cuentas: [] })
})

describe('reglas puras', () => {
  it('entiende montos escritos de varias maneras', () => {
    expect(parsearMonto('1.200.000')).toBe(1200000)
    expect(parsearMonto('$ 1.200.000,50')).toBe(1200000.5)
    expect(parsearMonto('1200000')).toBe(1200000)
    expect(parsearMonto('-350.000')).toBe(-350000)
    expect(parsearMonto('1,5')).toBe(1.5)
    expect(parsearMonto('')).toBeNull()
    expect(parsearMonto('abc')).toBeNull()
  })

  it('calcula la fecha de «los últimos N meses» y la dice en palabras', () => {
    expect(fechaDesdeMeses(3, new Date(2026, 9, 9))).toBe('2026-07-01')
    expect(fechaDesdeMeses(12, new Date(2026, 1, 15))).toBe('2025-02-01')
    expect(fechaLarga('2026-10-09')).toBe('9 de octubre de 2026')
    expect(descripcionPunto({ definido: true, modo: 'hoy', fecha: '2026-10-09' })).toBe('Desde el 9 de octubre de 2026 · Empezar desde hoy')
  })

  it('arma el aviso «te faltan extractos de: abril, mayo»', () => {
    const a = avisosFaltantes({ cuentas: [
      { cuenta_id: 'c1', nombre: 'Nu', faltan: ['2026-04', '2026-05'], faltan_texto: 'abril, mayo' },
      { cuenta_id: 'c2', nombre: 'Davi', faltan: [], faltan_texto: '' },
    ] })
    expect(a).toEqual([{ cuentaId: 'c1', nombre: 'Nu', texto: 'Te faltan extractos de: abril, mayo' }])
  })

  it('«decidir después» no insiste durante una semana', () => {
    expect(puntoDePartidaPospuesto()).toBe(false)
    posponerPuntoDePartida(1000)
    expect(puntoDePartidaPospuesto(1000 + 86400000)).toBe(true)
    expect(puntoDePartidaPospuesto(1000 + 8 * 86400000)).toBe(false)
  })
})

describe('elegir el punto de partida', () => {
  it('muestra las dos opciones con su explicación, ejemplo y ayuda para elegir', async () => {
    montar({ variante: 'primera', inicial: SIN_ELEGIR })
    const hoy = screen.getByTestId('modo-hoy')
    expect(hoy).toHaveTextContent('Empezar desde hoy')
    expect(hoy).toHaveTextContent('Recomendado')
    expect(hoy).toHaveTextContent('Ejemplo:')
    expect(screen.getByTestId('modo-historico')).toHaveTextContent('Recrear mi histórico')
    expect(screen.getByText(/¿Cuál elijo\?/)).toHaveTextContent('Si solo quieres controlar desde ahora')
    expect(screen.getByRole('button', { name: 'Elige una opción' })).toBeDisabled()
  })

  it('«Empezar desde hoy»: pide el saldo de cada cuenta y guarda con el ajuste si cambió', async () => {
    api.guardarPuntoDePartida.mockResolvedValue({ definido: true, modo: 'hoy', fecha: '2026-10-09', saldos: {}, anteriores: { correos: 0, extractos: 0 }, ajustados: 1 })
    const onGuardado = vi.fn()
    montar({ variante: 'primera', inicial: SIN_ELEGIR, onGuardado })
    fireEvent.click(screen.getByTestId('modo-hoy'))
    const saldo = screen.getByLabelText('Saldo de Bancolombia Ahorros')
    expect(saldo).toHaveValue('1500000') // arranca con lo que la app ya tiene
    fireEvent.change(saldo, { target: { value: '1.620.000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Empezar desde hoy' }))
    await waitFor(() => expect(api.guardarPuntoDePartida).toHaveBeenCalled())
    const cuerpo = api.guardarPuntoDePartida.mock.calls[0][0]
    expect(cuerpo.modo).toBe('hoy')
    expect(cuerpo.saldos.c1).toEqual({ actual: 1620000, inicial: 1620000 })
    expect(cuerpo.ajustar_saldos).toBe(true)
    expect(cuerpo).not.toHaveProperty('fecha')
    await waitFor(() => expect(onGuardado).toHaveBeenCalled())
    expect(await screen.findByTestId('punto-partida-resumen')).toHaveTextContent('Desde el 9 de octubre de 2026 · Empezar desde hoy')
  })

  it('sin cambiar ningún saldo no pide ajustes', async () => {
    api.guardarPuntoDePartida.mockResolvedValue({ definido: true, modo: 'hoy', fecha: '2026-10-09', saldos: {}, anteriores: { correos: 0, extractos: 0 } })
    montar({ variante: 'primera', inicial: SIN_ELEGIR })
    fireEvent.click(screen.getByTestId('modo-hoy'))
    fireEvent.click(screen.getByRole('button', { name: 'Empezar desde hoy' }))
    await waitFor(() => expect(api.guardarPuntoDePartida).toHaveBeenCalled())
    expect(api.guardarPuntoDePartida.mock.calls[0][0].ajustar_saldos).toBe(false)
  })

  it('«Recrear mi histórico»: elige 12 meses y guarda con saldos opcionales', async () => {
    api.guardarPuntoDePartida.mockResolvedValue({ definido: true, modo: 'historico', fecha: '2025-10-01', saldos: {}, anteriores: { correos: 0, extractos: 0 } })
    montar({ variante: 'primera', inicial: SIN_ELEGIR })
    fireEvent.click(screen.getByTestId('modo-historico'))
    fireEvent.click(screen.getByRole('button', { name: '12 meses' }))
    fireEvent.change(screen.getByLabelText('Saldo al inicio de Bancolombia Ahorros'), { target: { value: '800000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Recrear mi histórico' }))
    await waitFor(() => expect(api.guardarPuntoDePartida).toHaveBeenCalled())
    const cuerpo = api.guardarPuntoDePartida.mock.calls[0][0]
    expect(cuerpo).toMatchObject({ modo: 'historico', meses: 12 })
    expect(cuerpo.saldos.c1).toEqual({ actual: 1500000, inicial: 800000 })
  })

  it('«Decidir después» solo está en la primera vez', () => {
    const onPosponer = vi.fn()
    montar({ variante: 'primera', inicial: SIN_ELEGIR, onPosponer })
    fireEvent.click(screen.getByRole('button', { name: 'Decidir después' }))
    expect(onPosponer).toHaveBeenCalled()
  })
})

describe('Perfil: ver y cambiar el punto de partida', () => {
  const HISTORICO = {
    definido: true, modo: 'historico', fecha: '2026-07-01', saldos: {},
    anteriores: { correos: 3, extractos: 1 },
  }

  it('muestra lo elegido, lo que falta y el saldo reconstruido con su ajuste neutral', async () => {
    api.puntoDePartida.mockResolvedValue(HISTORICO)
    api.coberturaPuntoDePartida.mockResolvedValue({
      meses: [{ mes: '2026-07', etiqueta: 'julio 2026' }],
      cuentas: [{ cuenta_id: 'c1', nombre: 'Bancolombia Ahorros', faltan: ['2026-07', '2026-08'], faltan_texto: 'julio, agosto' }],
    })
    api.conciliacionPuntoDePartida.mockResolvedValue({ cuentas: [
      { cuenta_id: 'c1', nombre: 'Bancolombia Ahorros', coincide: false, diferencia: -100000 },
    ] })
    api.ajustarSaldosPuntoDePartida.mockResolvedValue({ ok: true, ajustados: 1 })
    montar({ variante: 'perfil' })
    const resumen = await screen.findByTestId('punto-partida-resumen')
    expect(resumen).toHaveTextContent('Desde el 1 de julio de 2026 · Recrear mi histórico')
    expect(screen.getByTestId('anteriores-ignorados')).toHaveTextContent('3 correos anteriores y 1 extracto anterior a tu fecha de inicio no se muestran.')
    expect(await screen.findByTestId('faltan-extractos')).toHaveTextContent('Te faltan extractos de: julio, agosto')
    expect(screen.getByTestId('saldo-reconstruido')).toHaveTextContent('Difiere en')

    fireEvent.click(screen.getByRole('button', { name: 'Ajustar el saldo' }))
    await waitFor(() => expect(api.ajustarSaldosPuntoDePartida).toHaveBeenCalled())
    expect(await screen.findByText(/ajusté el saldo de 1 cuenta/)).toBeInTheDocument()
    expect(recargar).toHaveBeenCalled()
  })

  it('mover la fecha hacia adelante pide confirmar que se oculta (y que no se borra nada)', async () => {
    api.puntoDePartida.mockResolvedValue({ ...HISTORICO, modo: 'hoy', fecha: '2025-01-01', anteriores: { correos: 0, extractos: 0 } })
    api.guardarPuntoDePartida.mockResolvedValue({ ...HISTORICO, modo: 'hoy', fecha: '2026-10-09' })
    montar({ variante: 'perfil' })
    fireEvent.click(await screen.findByRole('button', { name: 'Cambiar mi punto de partida' }))
    fireEvent.click(screen.getByTestId('modo-hoy'))
    fireEvent.click(screen.getByRole('button', { name: 'Empezar desde hoy' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Marca la casilla para confirmar')
    expect(api.guardarPuntoDePartida).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('checkbox', { name: /Entiendo que lo anterior/ }))
    expect(screen.getByText(/No se borra nada/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Empezar desde hoy' }))
    await waitFor(() => expect(api.guardarPuntoDePartida).toHaveBeenCalled())
  })

  it('mover la fecha hacia atrás no pide confirmación', async () => {
    api.puntoDePartida.mockResolvedValue({ ...HISTORICO, fecha: '2026-09-01', anteriores: { correos: 0, extractos: 0 } })
    api.guardarPuntoDePartida.mockResolvedValue({ ...HISTORICO, fecha: '2026-04-01' })
    montar({ variante: 'perfil' })
    fireEvent.click(await screen.findByRole('button', { name: 'Cambiar mi punto de partida' }))
    fireEvent.click(screen.getByTestId('modo-historico'))
    fireEvent.click(screen.getByRole('button', { name: '12 meses' }))
    expect(screen.queryByRole('checkbox', { name: /Entiendo que lo anterior/ })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Recrear mi histórico' }))
    await waitFor(() => expect(api.guardarPuntoDePartida).toHaveBeenCalled())
  })

  it('el servidor puede rechazar la fecha y se dice en llano', async () => {
    api.puntoDePartida.mockResolvedValue({ ...HISTORICO, anteriores: { correos: 0, extractos: 0 } })
    api.guardarPuntoDePartida.mockRejectedValue(new Error('Elige una fecha de hasta 24 meses atrás'))
    montar({ variante: 'perfil' })
    fireEvent.click(await screen.findByRole('button', { name: 'Cambiar mi punto de partida' }))
    fireEvent.click(screen.getByTestId('modo-historico'))
    fireEvent.click(screen.getByRole('button', { name: 'Recrear mi histórico' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('24 meses')
  })
})
