// Fechas de la tarjeta («Corte 15 oct · Pago hasta 4 nov») en «Tus cuentas, mes a mes» y en el Cierre de mes. Datos inventados.
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import EstadoPorCuenta from '../components/EstadoPorCuenta'
import CierreExtractos from '../components/CierreExtractos'
import { diaCorto, textoCorte, textoFechasTarjeta } from '../lib/fechasTarjeta'

const FECHAS = { corte: '2026-10-15', limite_pago: '2026-11-04', periodo_fin: '2026-10-14', estimado: false }

describe('textos de las fechas de la tarjeta', () => {
  it('corte y límite de pago, en español y sin ceros', () => {
    expect(textoFechasTarjeta(FECHAS)).toBe('Corte 15 oct · Pago hasta 4 nov')
    expect(textoCorte(FECHAS)).toBe('Corte 15 oct')
    expect(diaCorto('2026-06-14')).toBe('14 jun')
  })
  it('un corte calculado se dice aproximado y sin fecha de pago; sin corte no hay texto', () => {
    expect(textoFechasTarjeta({ corte: '2026-10-15', limite_pago: null, estimado: true })).toBe('Corte aprox. 15 oct')
    expect(textoFechasTarjeta(null)).toBe('')
    expect(textoFechasTarjeta({ corte: 'raro' })).toBe('')
  })
})

describe('«Tus cuentas, mes a mes»', () => {
  const meses = [{ clave: '2026-09', etiqueta: 'sep 26' }, { clave: '2026-10', etiqueta: 'oct 26' }]
  const celda = (mes, extra) => ({ mes, estado: 'vacio', movimientos: 0, por_revisar: 0, lista: [], en_otra_cuenta: [], ...extra })
  it('el extracto de octubre queda en octubre y la fila de la tarjeta dice el corte y el pago', () => {
    const cuentas = [{ id: 't', nombre: 'Nu Tarjeta', tipo: 'credito',
      meses: [celda('2026-09', { estado: 'conciliado', movimientos: 4 }), celda('2026-10', { estado: 'conciliado', movimientos: 16, tarjeta_fechas: FECHAS })] }]
    render(<EstadoPorCuenta cuentas={cuentas} meses={meses} />)
    expect(within(screen.getByTestId('mes-t-2026-10')).getByText('Corte 15 oct')).toBeInTheDocument()
    expect(within(screen.getByTestId('mes-t-2026-09')).queryByText(/Corte/)).not.toBeInTheDocument()
    expect(screen.getByTestId('fechas-tarjeta-t')).toHaveTextContent('Corte 15 oct · Pago hasta 4 nov')
  })
  it('sin fechas (o en una cuenta de ahorros) no aparece nada nuevo', () => {
    const cuentas = [{ id: 'a', nombre: 'Nu Ahorros', tipo: 'ahorro', meses: [celda('2026-09'), celda('2026-10', { estado: 'conciliado', movimientos: 3 })] }]
    render(<EstadoPorCuenta cuentas={cuentas} meses={meses} />)
    expect(screen.queryByTestId('fechas-tarjeta-a')).not.toBeInTheDocument()
  })
})

describe('Cierre de mes', () => {
  const cuenta = {
    cuenta_id: 't', nombre: 'Nu Tarjeta', tipo: 'credito', tarjeta: true, moneda: 'COP', estado: 'cuadra', sin_extracto: false,
    periodo: { desde: '2026-09-14', hasta: '2026-10-15', mes_completo: false }, empece: -200000, empece_origen: 'extracto', ingresos: 600000,
    gastos: 808000, otros: 0, otros_detalle: [], otros_total_movimientos: 0, termine: -408000, segun_extracto: -408000, diferencia: 0,
    historial_id: 'h', causas: [], acciones: [], motivo: null, base: {}, tarjeta_fechas: FECHAS,
  }
  const datos = { mes: '2026-10', etiqueta: 'Octubre 2026', parcial: false, moneda_base: 'COP', monedas_sin_tasa: [], meses: [], hay_datos: true,
    resumen_bancos: [{ banco: 'Nu', estado: 'cuadra', diferencia: 0 }], bancos: [{ banco: 'Nu', estado: 'cuadra', diferencia: 0, cuentas: [cuenta] }],
    total: { empece: -200000, ingresos: 600000, gastos: 808000, otros: 0, termine: -408000, cuentas: 1, cuadran: 1, no_cuadran: 0, sin_extracto: 0 } }
  it('la tarjeta muestra su corte y su pago bajo el periodo', () => {
    render(<MemoryRouter><CierreExtractos datos={datos} /></MemoryRouter>)
    expect(screen.getByTestId('fechas-tarjeta')).toHaveTextContent('Corte 15 oct · Pago hasta 4 nov')
  })
})
