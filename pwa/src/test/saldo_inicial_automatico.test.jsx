// «Saldo inicial automático»: tarjeta con explicación y «Volver a calcular»; y el Cierre dice desde qué mes cuadra.
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import SaldoInicialAutomatico from '../components/SaldoInicialAutomatico'
import CierreExtractos from '../components/CierreExtractos'

const INFO = { monto: 100000, fecha: '2026-02-28', explicacion: 'Es lo que tenías antes de tu primer extracto. No cuenta como ingreso ni gasto.' }

beforeEach(() => {
  api.cuadreSaldoInicialAutoRecalcular = vi.fn().mockResolvedValue({ texto: 'Actualicé con cuánto empezó tu cuenta: $80.000 al 31 ene 2026 (antes $100.000).' })
})

describe('Saldo inicial automático', () => {
  it('muestra el monto, la fecha y la explicación de una línea', () => {
    render(<SaldoInicialAutomatico cuentaId="c1" moneda="COP" info={INFO} />)
    expect(screen.getByText('Saldo inicial automático')).toBeTruthy()
    expect(screen.getByText(/Al 28 feb 2026/)).toBeTruthy()
    expect(screen.getByText('Es lo que tenías antes de tu primer extracto. No cuenta como ingreso ni gasto.')).toBeTruthy()
  })

  it('«Volver a calcular» llama al servidor y muestra lo que hizo', async () => {
    const onCambio = vi.fn()
    render(<SaldoInicialAutomatico cuentaId="c1" moneda="COP" info={INFO} onCambio={onCambio} />)
    const b = screen.getByRole('button', { name: /Volver a calcular/ })
    expect(b.className).toContain('min-h-11')
    fireEvent.click(b)
    await waitFor(() => expect(screen.getByText(/Actualicé con cuánto empezó tu cuenta/)).toBeTruthy())
    expect(api.cuadreSaldoInicialAutoRecalcular).toHaveBeenCalledWith('c1')
    expect(onCambio).toHaveBeenCalled()
  })

  it('si la persona lo deshizo, lo dice y ofrece volver a calcular', () => {
    render(<SaldoInicialAutomatico cuentaId="c1" moneda="COP" info={null} desactivado />)
    expect(screen.getByText(/no lo calculo solo/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Volver a calcular/ })).toBeTruthy()
  })

  it('sin ajuste y sin desactivar no pinta nada', () => {
    const { container } = render(<SaldoInicialAutomatico cuentaId="c1" moneda="COP" info={null} />)
    expect(container.firstChild).toBeNull()
  })
})

function cuenta(o = {}) {
  return {
    cuenta_id: 'c1', nombre: 'Nu de prueba', tipo: 'ahorro', tarjeta: false, moneda: 'COP', estado: 'cuadra', sin_extracto: false,
    etiqueta_extracto: null, periodo: { desde: '2026-04-01', hasta: '2026-04-30', mes_completo: true },
    empece: 150000, empece_origen: 'extracto', ingresos: 20000, gastos: 0, otros: 0, otros_detalle: [], otros_total_movimientos: 0,
    termine: 170000, segun_extracto: 170000, diferencia: 0, historial_id: 'h1', causas: [], acciones: [], motivo: null, base: {}, ...o,
  }
}

function datos(c) {
  return {
    mes: '2026-04', etiqueta: 'Abril 2026', parcial: false, moneda_base: 'COP', monedas_sin_tasa: [], meses: [], hay_datos: true,
    resumen_bancos: [{ banco: 'Nu', estado: c.estado, diferencia: 0 }],
    bancos: [{ banco: 'Nu', estado: c.estado, diferencia: 0, cuentas: [c], total: { empece: 150000, ingresos: 20000, gastos: 0, otros: 0, termine: 170000 } }],
    total: { empece: 150000, ingresos: 20000, gastos: 0, otros: 0, termine: 170000, cuentas: 1, cuadran: 1, no_cuadran: 0, sin_extracto: 0 },
  }
}

describe('Cierre de mes: desde dónde cuadra', () => {
  it('«Tu cuenta cuadra desde marzo» y el saldo inicial automático en la cuenta', () => {
    const c = cuenta({
      cuadre_desde: { estado: 'cuadra', desde: '2026-03', texto: 'Tu cuenta cuadra desde marzo.' },
      ajuste_inicial: { ...INFO, etiqueta: 'Saldo inicial automático' },
    })
    render(<MemoryRouter><CierreExtractos datos={datos(c)} /></MemoryRouter>)
    expect(screen.getByTestId('cuadra-desde').textContent).toContain('Tu cuenta cuadra desde marzo.')
    expect(screen.getByTestId('saldo-inicial-auto')).toBeTruthy()
  })

  it('«Primer mes que no cuadra» con la cifra, en tono de aviso', () => {
    const c = cuenta({
      estado: 'no_cuadra', segun_extracto: 160000, diferencia: -10000, motivo: 'Faltan movimientos.',
      cuadre_desde: { estado: 'no_cuadra', desde: null, primer_mes_malo: '2026-03', texto: 'Primer mes que no cuadra: marzo por $10.000.' },
    })
    render(<MemoryRouter><CierreExtractos datos={datos(c)} /></MemoryRouter>)
    const t = screen.getByTestId('cuadra-desde')
    expect(t.textContent).toContain('Primer mes que no cuadra: marzo por $10.000.')
    expect(t.className).toContain('text-danger')
  })
})
