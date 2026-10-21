// La tarjeta es deuda: «Debes · Cupo · Disponible», barra de cupo, corte, pago mínimo; sin saldo ni ingresos. Datos inventados.
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import DeudaTarjeta from '../components/DeudaTarjeta'
import EstadoPorCuenta from '../components/EstadoPorCuenta'
import CierreExtractos from '../components/CierreExtractos'
import { datosDeuda, textoCortePago } from '../lib/deudaTarjeta'

const VISTA = {
  cuenta_id: 't', tarjeta: true, deuda: 350000, cupo: 1000000, disponible: 650000, uso_pct: 35, corte: '2026-10-15',
  limite_pago: '2026-11-04', pago_minimo: 42000, con_extracto: true, a_favor: false,
}
const fmt = (v) => `$${Math.round(v).toLocaleString('es-CO')}`

describe('textos de la deuda', () => {
  it('Debes, cupo, disponible y uso del cupo', () => {
    const d = datosDeuda(VISTA, fmt)
    expect(d.debes).toBe('$350.000')
    expect(d.cupo).toBe('$1.000.000')
    expect(d.disponible).toBe('$650.000')
    expect(d.usoPct).toBe(35)
    expect(d.pagoMinimo).toBe('$42.000')
    expect(d.corte).toBe('Corte 15 oct · Pago hasta 4 nov')
    expect(textoCortePago({})).toBe('')
  })
  it('sin cupo no se inventa ni barra ni disponible; sin deuda queda al día', () => {
    const d = datosDeuda({ tarjeta: true, deuda: 0, cupo: null }, fmt)
    expect(d.cupo).toBeNull()
    expect(d.usoPct).toBeNull()
    expect(d.alDia).toBe(true)
    expect(datosDeuda(null, fmt)).toBeNull()
  })
})

describe('<DeudaTarjeta>', () => {
  it('muestra la barra de uso del cupo, el corte y el pago mínimo, sin la palabra saldo ni ingresos', () => {
    const { container } = render(<DeudaTarjeta vista={VISTA} />)
    expect(screen.getByTestId('deuda-resumen')).toHaveTextContent('Debes')
    expect(screen.getByTestId('deuda-resumen')).toHaveTextContent('Cupo')
    expect(screen.getByTestId('deuda-resumen')).toHaveTextContent('Disponible')
    expect(screen.getByRole('progressbar', { name: 'Uso del cupo' })).toHaveAttribute('aria-valuenow', '35')
    expect(screen.getByTestId('corte-pago')).toHaveTextContent('Corte 15 oct · Pago hasta 4 nov')
    expect(screen.getByTestId('pago-minimo')).toHaveTextContent('Pago mínimo')
    expect(container.textContent).not.toMatch(/saldo|ingresos/i)
  })
})

describe('«Tus cuentas, mes a mes» con tarjeta', () => {
  it('la tarjeta trae su bloque de deuda y la de ahorros no', () => {
    const meses = [{ clave: '2026-10', etiqueta: 'oct 26' }]
    const celda = { mes: '2026-10', estado: 'conciliado', movimientos: 3, por_revisar: 0, lista: [], en_otra_cuenta: [] }
    const cuentas = [
      { id: 't', nombre: 'Nu Tarjeta', tipo: 'credito', meses: [celda] },
      { id: 'a', nombre: 'Nu Ahorros', tipo: 'ahorro', meses: [celda] },
    ]
    render(<EstadoPorCuenta cuentas={cuentas} meses={meses} deudas={{ t: VISTA }} />)
    expect(within(screen.getByTestId('cuenta-t')).getByTestId('deuda-tarjeta')).toBeInTheDocument()
    expect(within(screen.getByTestId('cuenta-a')).queryByTestId('deuda-tarjeta')).not.toBeInTheDocument()
  })
})

describe('Cierre de mes de la tarjeta', () => {
  const tarjeta = {
    debia_inicio: 200000, compras_cargos: 600000, intereses: 8000, pagos: 400000, debo_calculado: 408000, segun_extracto: 408000,
    diferencia: 0, cuadra: true,
  }
  const cuenta = (extra = {}) => ({
    cuenta_id: 't', nombre: 'Nu Tarjeta', tipo: 'credito', tarjeta: true, moneda: 'COP', estado: 'cuadra', sin_extracto: false,
    periodo: { desde: '2026-09-14', hasta: '2026-10-15', mes_completo: false }, empece: -200000, empece_origen: 'extracto',
    ingresos: 0, gastos: 0, otros: 0, otros_detalle: [], otros_total_movimientos: 0, termine: -408000, segun_extracto: -408000,
    diferencia: 0, historial_id: 'h', causas: [], acciones: [], motivo: null, base: {}, tarjeta_cuadre: tarjeta, ...extra,
  })
  const datos = (c) => ({ mes: '2026-10', etiqueta: 'Octubre 2026', parcial: false, moneda_base: 'COP', monedas_sin_tasa: [], meses: [], hay_datos: true,
    resumen_bancos: [{ banco: 'Nu', estado: c.estado, diferencia: 0 }], bancos: [{ banco: 'Nu', estado: c.estado, diferencia: 0, cuentas: [c] }],
    total: { empece: 0, ingresos: 0, gastos: 0, otros: 0, termine: 0, cuentas: 1, cuadran: 1, no_cuadran: 0, sin_extracto: 0 } })

  it('usa el formato de deuda: debía, compras y cargos, intereses, pagos, debo al corte y según tu extracto', () => {
    render(<MemoryRouter><CierreExtractos datos={datos(cuenta())} /></MemoryRouter>)
    const b = screen.getByTestId('cierre-tarjeta-deuda')
    for (const t of ['Debía al inicio', 'Compras y cargos', 'Intereses', 'Pagos', 'Debo al corte (calculado)', 'Según tu extracto', 'Cuadra ✓']) {
      expect(within(b).getByText(t)).toBeInTheDocument()
    }
    expect(within(b).queryByText('Empecé con')).not.toBeInTheDocument()
    expect(within(b).queryByText('Ingresos')).not.toBeInTheDocument()
  })
  it('si no cuadra dice por cuánto', () => {
    const c = cuenta({ estado: 'no_cuadra', diferencia: 35000, tarjeta_cuadre: { ...tarjeta, cuadra: false, diferencia: 35000, debo_calculado: 443000 } })
    render(<MemoryRouter><CierreExtractos datos={datos(c)} /></MemoryRouter>)
    expect(within(screen.getByTestId('cierre-tarjeta-deuda')).getByText(/No cuadra ✕ por \$\s?35\.000/)).toBeInTheDocument()
  })
})
