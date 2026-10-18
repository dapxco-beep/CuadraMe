// Cierre de mes contra el extracto: textos puros, pantalla por banco y estados (cuadra / no cuadra / sin extracto).
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import { conSigno, estadoCuenta, textoBanco, textoPeriodo } from '../lib/cierreExtractos'
import CierreExtractos from '../components/CierreExtractos'
import { formatMoneda } from '../lib/format'

const fmt = (v, m) => formatMoneda(v, m || 'COP').replace(/\s/g, ' ')

function cuenta(o = {}) {
  return {
    cuenta_id: 'c1', nombre: 'Alfa Ahorros', tipo: 'ahorro', tarjeta: false, moneda: 'COP', estado: 'cuadra', sin_extracto: false,
    etiqueta_extracto: null, periodo: { desde: '2026-05-01', hasta: '2026-05-31', mes_completo: true },
    empece: 500000, empece_origen: 'extracto', ingresos: 300000, gastos: 100000, otros: 0, otros_detalle: [], otros_total_movimientos: 0,
    termine: 700000, segun_extracto: 700000, diferencia: 0, historial_id: 'h1', causas: [], acciones: [], motivo: null, base: {}, ...o,
  }
}

function datos(bancos, extra = {}) {
  return {
    mes: '2026-05', etiqueta: 'Mayo 2026', parcial: false, moneda_base: 'COP', monedas_sin_tasa: [], meses: [], hay_datos: true,
    resumen_bancos: bancos.map((b) => ({ banco: b.banco, estado: b.estado, diferencia: b.diferencia })),
    bancos, total: { empece: 600000, ingresos: 380000, gastos: 120000, otros: 0, termine: 860000, cuentas: 2, cuadran: 1, no_cuadran: 1, sin_extracto: 0 },
    ...extra,
  }
}

const montar = (d, props = {}) => render(<MemoryRouter><CierreExtractos datos={d} {...props} /></MemoryRouter>)

describe('textos del cierre contra el extracto', () => {
  it('resumen por banco', () => {
    const f = (v) => `$${v}`
    expect(textoBanco({ banco: 'Nu', estado: 'cuadra' }, f)).toBe('Nu: ✓')
    expect(textoBanco({ banco: 'Nequi', estado: 'no_cuadra', diferencia: 39496 }, f)).toBe('Nequi: ✕ $39496')
    expect(textoBanco({ banco: 'Beta', estado: 'sin_extracto' }, f)).toBe('Beta: sin extracto')
  })
  it('estado de cuenta y signos', () => {
    expect(estadoCuenta({ estado: 'cuadra' }, fmt)).toBe('Cuadra')
    expect(estadoCuenta({ estado: 'no_cuadra', diferencia: -40000, moneda: 'COP' }, fmt)).toContain('No cuadra por')
    expect(estadoCuenta({ estado: 'sin_extracto' }, fmt)).toBe('Sin extracto')
    expect(conSigno(300000, fmt, 'COP')).toMatch(/^\+/)
    expect(conSigno(-5000, fmt, 'COP')).toMatch(/^−/)
    expect(conSigno(0, fmt, 'COP')).not.toMatch(/^[+−]/)
  })
  it('periodo solo si no es el mes calendario', () => {
    expect(textoPeriodo({ mes_completo: true })).toBe('')
    expect(textoPeriodo({ desde: '2026-05-05', hasta: '2026-06-04', mes_completo: false })).toBe('Del 5 may al 4 jun')
  })
})

describe('pantalla del cierre por banco', () => {
  it('muestra empecé, ingresos, gastos, terminé y que cuadra', () => {
    montar(datos([{ banco: 'Alfa', estado: 'cuadra', diferencia: 0, cuentas: [cuenta()] }]))
    const c = screen.getByTestId('cierre-cuenta')
    expect(within(c).getByText('Empecé con')).toBeInTheDocument()
    expect(within(c).getByText('Ingresos')).toBeInTheDocument()
    expect(within(c).getByText('Gastos')).toBeInTheDocument()
    expect(within(c).getByText('Terminé con')).toBeInTheDocument()
    expect(within(c).getByText('Según tu extracto')).toBeInTheDocument()
    expect(within(c).getByText('Cuadra')).toBeInTheDocument()
    expect(screen.getByTestId('resumen-bancos')).toHaveTextContent('Alfa: ✓')
  })

  it('un mes que no cuadra dice por cuánto, la causa y ofrece la acción y «Ver qué falta»', async () => {
    api.cuadreQueFalta = vi.fn().mockResolvedValue({
      sin_pareja_en_tus_movimientos: [{ fecha: '2026-05-20', descripcion: 'Abono prueba', monto: 40000, tipo: 'income' }], sin_respaldo_en_el_extracto: [],
    })
    const c = cuenta({
      estado: 'no_cuadra', diferencia: 40000, termine: 660000, segun_extracto: 700000,
      motivo: 'Falta importar 1 línea del extracto: ingreso de $40.000 del 20 may.',
      acciones: [{ tipo: 'importar_lineas', historial_id: 'h1', fingerprints: ['fp'], texto: 'Importar la línea que falta', confirmacion: 'Se agregará.' }],
    })
    montar(datos([{ banco: 'Beta', estado: 'no_cuadra', diferencia: 40000, cuentas: [c] }]))
    expect(screen.getByTestId('resumen-bancos')).toHaveTextContent('Beta: ✕')
    expect(screen.getAllByText(/No cuadra por/).length).toBeGreaterThan(0)
    const d = screen.getByTestId('cierre-diagnostico')
    expect(d).toHaveTextContent('Falta importar 1 línea del extracto')
    expect(within(d).getByRole('button', { name: 'Importar la línea que falta' })).toBeInTheDocument()
    fireEvent.click(within(d).getByRole('button', { name: /Ver qué falta/ }))
    await waitFor(() => expect(api.cuadreQueFalta).toHaveBeenCalledWith('c1', 'h1'))
    expect(await screen.findByText('Abono prueba', { exact: false })).toBeInTheDocument()
  })

  it('un mes sin extracto se etiqueta «Sin extracto» y no pinta «Según tu extracto»', () => {
    const c = cuenta({ estado: 'sin_extracto', sin_extracto: true, etiqueta_extracto: 'Sin extracto', segun_extracto: null, diferencia: null, empece_origen: 'calculado', historial_id: null })
    montar(datos([{ banco: 'Alfa', estado: 'sin_extracto', diferencia: null, cuentas: [c] }]))
    expect(screen.getAllByText('Sin extracto').length).toBeGreaterThan(0)
    expect(screen.queryByText('Según tu extracto')).toBeNull()
    expect(screen.getByText(/lo que calculó la app/)).toBeInTheDocument()
  })

  it('«Otros movimientos» se despliega con el detalle', () => {
    const c = cuenta({ otros: -25000, termine: 675000, otros_total_movimientos: 1,
      otros_detalle: [{ fecha: '2026-05-20', descripcion: 'Pase a Beta', monto: -25000, clase: 'traslado' }] })
    montar(datos([{ banco: 'Alfa', estado: 'cuadra', diferencia: 0, cuentas: [c] }]))
    expect(screen.queryByTestId('otros-detalle')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Ver el detalle/ }))
    expect(screen.getByTestId('otros-detalle')).toHaveTextContent('Pase a Beta')
    expect(screen.getByTestId('otros-detalle')).toHaveTextContent('Pasaste plata entre tus cuentas')
  })

  it('banco con cuenta y tarjeta: cada una con su nombre y un total del banco', () => {
    const a = cuenta()
    const t = cuenta({ cuenta_id: 'c2', nombre: 'Alfa Tarjeta', tarjeta: true, empece: -200000, termine: -250000, segun_extracto: -250000 })
    montar(datos([{ banco: 'Alfa', estado: 'cuadra', diferencia: 0, cuentas: [a, t], total: { empece: 300000, ingresos: 300000, gastos: 150000, otros: 0, termine: 450000 } }]))
    expect(screen.getAllByTestId('cierre-cuenta')).toHaveLength(2)
    expect(screen.getByText(/Alfa Tarjeta · Tarjeta/)).toBeInTheDocument()
    expect(screen.getByTestId('total-banco')).toHaveTextContent('Total Alfa')
    expect(screen.getByTestId('cierre-total')).toHaveTextContent('Todas tus cuentas')
  })

  it('sin movimientos ese mes muestra un vacío claro', () => {
    montar(datos([], { hay_datos: false, bancos: [] }))
    expect(screen.getByTestId('cierre-sin-datos')).toHaveTextContent('No hay movimientos en mayo 2026')
  })
})
