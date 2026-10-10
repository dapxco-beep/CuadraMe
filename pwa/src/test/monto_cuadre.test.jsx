import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from './userEvent.js'
import InputMonto from '../components/InputMonto'
import { canonicoDesdeEscrito, canonicoDesdePegado, mostrarMonto } from '../lib/monto'
import { estadoCuadre } from '../lib/cuadre'

describe('formato de montos', () => {
  it('pasa de lo escrito al valor canónico y de vuelta', () => {
    expect(canonicoDesdeEscrito('1.250.000')).toBe('1250000')
    expect(canonicoDesdeEscrito('1.250.000,5')).toBe('1250000.5')
    expect(canonicoDesdeEscrito('0,')).toBe('0.')
    expect(canonicoDesdeEscrito('1,2345')).toBe('1.23')
    expect(canonicoDesdeEscrito('12,5', { decimales: false })).toBe('125')
    expect(canonicoDesdeEscrito('-350.000', { negativo: true })).toBe('-350000')
    expect(mostrarMonto('1250000')).toBe('1.250.000')
    expect(mostrarMonto('1250000.5')).toBe('1.250.000,5')
    expect(mostrarMonto('')).toBe('')
    expect(canonicoDesdePegado('$ 1.250.000')).toBe('1250000')
    expect(canonicoDesdePegado('1,250,000.50')).toBe('1250000.5')
  })
})

function Demo({ entero = false }) {
  const [v, setV] = useState('')
  return (
    <>
      <InputMonto aria-label="Monto" value={v} onValor={setV} entero={entero} />
      <output data-testid="enviado">{v}</output>
    </>
  )
}

describe('InputMonto', () => {
  it('da formato de miles en vivo, usa teclado numérico y envía un valor numérico', async () => {
    render(<Demo entero />)
    const campo = screen.getByLabelText('Monto')
    expect(campo).toHaveAttribute('inputmode', 'numeric')
    await userEvent.type(campo, '1250000')
    expect(campo).toHaveValue('1.250.000')
    expect(Number(screen.getByTestId('enviado').textContent)).toBe(1250000)
  })

  it('acepta la coma decimal', async () => {
    render(<Demo />)
    const campo = screen.getByLabelText('Monto')
    expect(campo).toHaveAttribute('inputmode', 'decimal')
    await userEvent.type(campo, '1250,75')
    expect(campo).toHaveValue('1.250,75')
    expect(screen.getByTestId('enviado').textContent).toBe('1250.75')
  })

  it('no pierde el cursor al escribir en medio del número', async () => {
    render(<Demo entero />)
    const campo = screen.getByLabelText('Monto')
    await userEvent.type(campo, '1250000')
    campo.setSelectionRange(1, 1) // después del primer dígito
    await userEvent.keyboard('9')
    expect(campo).toHaveValue('19.250.000')
    expect(campo.selectionStart).toBe(2)
  })

  it('borra un dígito aunque el cursor esté junto a un punto', async () => {
    render(<Demo entero />)
    const campo = screen.getByLabelText('Monto')
    await userEvent.type(campo, '1250')
    expect(campo).toHaveValue('1.250')
    campo.setSelectionRange(2, 2) // justo después del punto
    await userEvent.keyboard('{Backspace}')
    expect(campo).toHaveValue('250')
  })

  it('pegar un monto con formato lo normaliza', () => {
    render(<Demo />)
    const campo = screen.getByLabelText('Monto')
    fireEvent.paste(campo, { clipboardData: { getData: () => '$ 2.500.000' } })
    expect(campo).toHaveValue('2.500.000')
  })
})

describe('estadoCuadre', () => {
  const bolsillo = (saldo_total, disponible_real, comp = 0) => ({
    saldo_total, disponible_real, recurrentes_pendientes_mes: comp, aportes_comprometidos_mes: 0,
  })
  const cta = (saldo) => ({ id: String(saldo), saldo })

  it('sin cuentas o con todo en $0 no afirma que cuadre', () => {
    expect(estadoCuadre({ cuentas: [], bolsillo: bolsillo(0, 0) }).estado).toBe('sin_datos')
    expect(estadoCuadre({ cuentas: [cta(0)], bolsillo: bolsillo(0, 0) }).estado).toBe('sin_datos')
  })
  it('saldo $0 con compromisos es parcial, no «te faltan»', () => {
    expect(estadoCuadre({ cuentas: [cta(0)], bolsillo: bolsillo(0, -200000, 200000) }).estado).toBe('parcial')
  })
  it('una cuenta en $0 sin movimientos vuelve parcial el cuadre', () => {
    const r = estadoCuadre({ cuentas: [cta(500000), cta(0)], bolsillo: bolsillo(500000, 400000), movimientos: [] })
    expect(r.estado).toBe('parcial')
  })
  it('con datos reales dice cuadra o falta', () => {
    const ok = estadoCuadre({ cuentas: [cta(1000000)], bolsillo: bolsillo(1000000, 400000), movimientos: [{}] })
    expect(ok.estado).toBe('cuadra')
    const mal = estadoCuadre({ cuentas: [cta(100000)], bolsillo: bolsillo(100000, -50000, 150000), movimientos: [{}] })
    expect(mal.estado).toBe('falta')
  })
})
