import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from './userEvent.js'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import ComprasACuotas from '../components/ComprasACuotas'
import ResumenSaldo from '../components/ResumenSaldo'
import { calcularCuota, comprometidoEsteMes, mesAnio } from '../lib/cuotas'

const CUENTA = {
  id: 't1', nombre: 'Nu', moneda: 'COP', tipo: 'credito', saldo: -1200000,
  tarjeta: { proximo_corte: '2026-10-15' },
}
const PLAN = {
  id: 'p1', descripcion: 'Nevera', cuota_mensual: 100000, num_cuotas: 12, numero_actual: 3, pagadas: 2,
  saldo_pendiente: 1000000, termina_en: '2027-09', terminado: false, vence_este_mes: true, total: 1200000,
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    cuotasTarjeta: vi.fn().mockResolvedValue({ comprometido_mes: 100000, planes: [PLAN] }),
    crearCuotaTarjeta: vi.fn().mockResolvedValue({}),
    pagarCuotaTarjeta: vi.fn().mockResolvedValue({}),
    eliminarCuotaTarjeta: vi.fn().mockResolvedValue({ ok: true }),
  })
})

describe('calcularCuota', () => {
  it('sin interés divide en partes iguales', () => {
    expect(calcularCuota(1200000, 12, 0)).toBe(100000)
    expect(calcularCuota(1200000, 12)).toBe(100000)
  })
  it('con 2% mensual da la cuota francesa (94.559,6 -> 94.560)', () => {
    expect(calcularCuota(1000000, 12, 2)).toBe(94560)
  })
  it('entradas inválidas dan 0', () => {
    expect(calcularCuota(0, 12, 0)).toBe(0)
    expect(calcularCuota(1000, 0, 0)).toBe(0)
  })
  it('ayudas', () => {
    expect(mesAnio('2027-09')).toBe('sep 2027')
    expect(comprometidoEsteMes([PLAN, { ...PLAN, vence_este_mes: false }, { ...PLAN, terminado: true }])).toBe(100000)
  })
})

describe('Compras a cuotas en la tarjeta', () => {
  it('lista qué es, cuota, "va en 3 de 12", saldo pendiente, cuándo termina y el comprometido', async () => {
    render(<ComprasACuotas cuenta={CUENTA} />)
    const plan = await screen.findByTestId('plan-cuotas')
    expect(plan).toHaveTextContent('Nevera')
    expect(plan).toHaveTextContent(/\$\s?100\.000\/mes/)
    expect(plan).toHaveTextContent('Va en 3 de 12')
    expect(plan).toHaveTextContent(/Saldo pendiente \$\s?1\.000\.000/)
    expect(plan).toHaveTextContent('Termina en sep 2027')
    expect(screen.getByTestId('comprometido-cuotas')).toHaveTextContent(/Comprometido en cuotas este mes:\s*\$\s?100\.000/)
  })

  it('agregar calcula la cuota con y sin interés y guarda sin tocar saldos', async () => {
    render(<ComprasACuotas cuenta={CUENTA} />)
    await userEvent.click(await screen.findByText('Agregar compra a cuotas'))
    fireEvent.change(screen.getByLabelText('Qué compraste'), { target: { value: 'TV' } })
    fireEvent.change(screen.getByLabelText('Valor de la compra'), { target: { value: '1.200.000' } })
    fireEvent.change(screen.getByLabelText('Número de cuotas'), { target: { value: '12' } })
    expect(screen.getByTestId('vista-cuota')).toHaveTextContent(/\$\s?100\.000/)
    expect(screen.getByTestId('vista-cuota')).toHaveTextContent('15 oct')

    fireEvent.change(screen.getByLabelText('Valor de la compra'), { target: { value: '1000000' } })
    fireEvent.change(screen.getByLabelText('Tasa mensual'), { target: { value: '2' } })
    expect(screen.getByTestId('vista-cuota')).toHaveTextContent(/\$\s?94\.560/)

    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(api.crearCuotaTarjeta).toHaveBeenCalledWith({
      cuenta_id: 't1', descripcion: 'TV', total: 1000000, num_cuotas: 12, tasa_mensual: 2,
    }))
  })

  it('valida antes de enviar', async () => {
    render(<ComprasACuotas cuenta={CUENTA} />)
    await userEvent.click(await screen.findByText('Agregar compra a cuotas'))
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/qué compraste/)
    expect(api.crearCuotaTarjeta).not.toHaveBeenCalled()
  })

  it('marcar pagada y quitar llaman al backend', async () => {
    render(<ComprasACuotas cuenta={CUENTA} />)
    await userEvent.click(await screen.findByText('Marcar cuota pagada'))
    expect(api.pagarCuotaTarjeta).toHaveBeenCalledWith('p1')
    await userEvent.click(screen.getByLabelText('Quitar Nevera'))
    await userEvent.click(screen.getByText('Sí'))
    await waitFor(() => expect(api.eliminarCuotaTarjeta).toHaveBeenCalledWith('p1'))
  })

  it('sin planes invita a agregar y si el backend falla no rompe', async () => {
    api.cuotasTarjeta.mockRejectedValue(new Error('sin red'))
    render(<ComprasACuotas cuenta={CUENTA} />)
    expect(await screen.findByText(/agrégalo para ver cuánto te toca pagar/)).toBeInTheDocument()
  })
})

describe('Resumen de saldo con cuotas', () => {
  const resumen = { total_cop: 500000, disponible_cop: 1700000, deudas_tarjeta_cop: 1200000, por_moneda: {}, por_tipo: {} }
  it('informa lo que vence en cuotas este mes sin restarlo dos veces', () => {
    render(<ResumenSaldo resumen={resumen} bolsillo={{ recurrentes_pendientes_mes: 0, aportes_comprometidos_mes: 0, cuotas_tarjeta_mes: 100000 }} />)
    expect(screen.getByText('De eso, en cuotas este mes')).toBeInTheDocument()
  })
  it('sin cuotas no muestra la fila', () => {
    render(<ResumenSaldo resumen={resumen} bolsillo={{ recurrentes_pendientes_mes: 0, aportes_comprometidos_mes: 0, cuotas_tarjeta_mes: 0 }} />)
    expect(screen.queryByText('De eso, en cuotas este mes')).not.toBeInTheDocument()
  })
})
