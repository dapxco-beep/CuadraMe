import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [], cargando: false, error: '', recargar: api.recargarCuentas }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Cuentas from '../screens/Cuentas'
import { datosCuentaNueva, leerMonto, validarTarjetaNueva } from '../lib/cuentaNueva'

function montar(ui) {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    recargarCuentas: vi.fn(),
    crearCuenta: vi.fn().mockResolvedValue({ id: 'n1' }),
  })
})

describe('leerMonto', () => {
  it('entiende formatos colombianos', () => {
    expect(leerMonto('1.200.000')).toBe(1200000)
    expect(leerMonto('1.200,50')).toBe(1200.5)
    expect(leerMonto('1200.5')).toBe(1200.5)
    expect(leerMonto('850.000')).toBe(850000)
    expect(leerMonto('')).toBe(0)
  })
})

describe('datosCuentaNueva', () => {
  const base = { nombre: ' Nu ', icono: '💳', moneda: 'COP', saldo: '', cupo: '', debes: '', corte: '', pago: '', tasa: '' }
  it('tarjeta: lo que debes (positivo) se guarda como saldo negativo', () => {
    const d = datosCuentaNueva({ ...base, tipo: 'credito', cupo: '5.000.000', debes: '1.200.000', corte: '15', pago: '30', tasa: '28.5' })
    expect(d).toMatchObject({ nombre: 'Nu', saldo: -1200000, cupo_total: 5000000, dia_corte: 15, dia_pago: 30, tasa_ea: 28.5 })
  })
  it('tarjeta: si ya escribió negativo no se invierte de nuevo', () => {
    expect(datosCuentaNueva({ ...base, tipo: 'credito', debes: '-300000' }).saldo).toBe(-300000)
  })
  it('cuenta normal sigue usando el saldo tal cual', () => {
    const d = datosCuentaNueva({ ...base, tipo: 'ahorro', saldo: '2.500.000' })
    expect(d.saldo).toBe(2500000)
    expect(d.cupo_total).toBeUndefined()
  })
  it('valida días y tasa', () => {
    expect(validarTarjetaNueva({ corte: '40', pago: '', tasa: '' })).toMatch(/entre 1 y 31/)
    expect(validarTarjetaNueva({ corte: '', pago: '', tasa: '300' })).toMatch(/0 y 200/)
    expect(validarTarjetaNueva({ corte: '15', pago: '30', tasa: '28' })).toBeNull()
  })
})

describe('Formulario de cuenta nueva con tarjeta de crédito', () => {
  it('pide cupo, cuánto debes, corte, pago y tasa; 1.200.000 se guarda como -1200000', async () => {
    montar(<Cuentas />)
    await userEvent.click(await screen.findByLabelText('Nueva cuenta'))
    expect(screen.getByLabelText('Saldo actual')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Tarjeta de crédito/ }))
    expect(screen.queryByLabelText('Saldo actual')).not.toBeInTheDocument()
    expect(screen.getByText('¿Cuánto debes hoy?')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Nombre de la cuenta'), { target: { value: 'Nu Crédito' } })
    fireEvent.change(screen.getByLabelText('Cupo total'), { target: { value: '5.000.000' } })
    fireEvent.change(screen.getByLabelText('Cuánto debes hoy'), { target: { value: '1.200.000' } })
    fireEvent.change(screen.getByLabelText('Día de corte'), { target: { value: '15' } })
    fireEvent.change(screen.getByLabelText('Día de pago'), { target: { value: '30' } })
    fireEvent.change(screen.getByLabelText('Tasa efectiva anual'), { target: { value: '28.5' } })
    await userEvent.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    await waitFor(() => expect(api.crearCuenta).toHaveBeenCalled())
    expect(api.crearCuenta.mock.calls[0][0]).toMatchObject({
      tipo: 'credito', saldo: -1200000, cupo_total: 5000000, dia_corte: 15, dia_pago: 30, tasa_ea: 28.5,
    })
  })

  it('no deja crear con un día de corte inválido', async () => {
    montar(<Cuentas />)
    await userEvent.click(await screen.findByLabelText('Nueva cuenta'))
    await userEvent.click(screen.getByRole('button', { name: /Tarjeta de crédito/ }))
    fireEvent.change(screen.getByLabelText('Día de corte'), { target: { value: '45' } })
    fireEvent.change(screen.getByLabelText('Nombre de la cuenta'), { target: { value: 'Mi tarjeta' } })
    await userEvent.click(screen.getByRole('button', { name: 'Crear cuenta' }))
    expect(api.crearCuenta).not.toHaveBeenCalled()
  })
})
