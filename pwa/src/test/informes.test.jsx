import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ iconoDe: () => '🛒', nombres: [], categorias: [] }),
}))

import {
  abreviarCOP, cuadriculaSemanas, escala, pctTexto, rangoPeriodo, rangoValido, seleccionarMeses,
} from '../lib/informe'
import GraficoTendencia from '../components/GraficoTendencia'
import SelectorPeriodo from '../components/SelectorPeriodo'
import Informe, { segmentosDona } from '../screens/Informe'
import Wrapped from '../screens/Wrapped'
import { DialogosProvider } from '../lib/DialogosContext'

describe('cálculos puros de informes', () => {
  it('abrevia montos: $1,2M, $450k, $950, negativos', () => {
    expect(abreviarCOP(1_234_567)).toBe('$1,2M')
    expect(abreviarCOP(450_000)).toBe('$450k')
    expect(abreviarCOP(950)).toBe('$950')
    expect(abreviarCOP(-2_500_000)).toBe('-$2,5M')
    expect(abreviarCOP(0)).toBe('$0')
  })

  it('escala del eje con pasos bonitos (calculada a mano)', () => {
    // 1.25M / 4 = 312.500 -> paso 500.000; techo 1.5M
    expect(escala(0, 1_250_000).ticks).toEqual([0, 500_000, 1_000_000, 1_500_000])
    // con negativos: -200k..800k -> paso 250k, de -250k a 1M
    const e = escala(-200_000, 800_000)
    expect(e.min).toBe(-250_000)
    expect(e.max).toBe(1_000_000)
    expect(e.ticks).toHaveLength(6)
    // sin datos no rompe
    expect(escala(0, 0).max).toBeGreaterThan(0)
  })

  it('periodos de fecha respecto a un día fijo (jueves 15-oct-2026)', () => {
    const hoy = new Date(2026, 9, 15)
    expect(rangoPeriodo('mes_pasado', hoy)).toEqual({ desde: '2026-09-01', hasta: '2026-09-30' })
    expect(rangoPeriodo('este_mes', hoy)).toEqual({ desde: '2026-10-01', hasta: '2026-10-15' })
    expect(rangoPeriodo('5_semanas', hoy)).toEqual({ desde: '2026-09-11', hasta: '2026-10-15' }) // 35 días
    expect(rangoPeriodo('3_meses', hoy).desde).toBe('2026-08-01')
    expect(rangoPeriodo('semana', hoy).desde).toBe('2026-10-12') // lunes
    expect(rangoPeriodo('semana_pasada', hoy)).toEqual({ desde: '2026-10-05', hasta: '2026-10-11' })
  })

  it('valida rangos personalizados', () => {
    expect(rangoValido('2026-10-01', '2026-10-15')).toBe(true)
    expect(rangoValido('2026-10-15', '2026-10-01')).toBe(false)
    expect(rangoValido('2025-01-01', '2026-10-01')).toBe(false) // más de 400 días
    expect(rangoValido('', '2026-10-01')).toBe(false)
  })

  it('calendario lunes-domingo con huecos', () => {
    const dias = ['2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05'].map((dia) => ({ dia, gasto: 0 }))
    const s = cuadriculaSemanas(dias)
    expect(s).toHaveLength(2)
    expect(s[0].map((c) => c && c.dia)).toEqual([null, null, null, '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'])
    expect(s[1][0].dia).toBe('2026-10-05')
    expect(s[1].filter(Boolean)).toHaveLength(1)
  })

  it('selecciona los últimos N meses y salta los vacíos', () => {
    const m = (mes, g) => ({ mes, ingresos: g, gastos: g, ahorro: 0, num_movimientos: g ? 1 : 0 })
    const serie = [m('2026-05', 0), m('2026-06', 5), m('2026-07', 0), m('2026-08', 7), m('2026-09', 0), m('2026-10', 9)]
    expect(seleccionarMeses(serie, 3).map((x) => x.mes)).toEqual(['2026-08', '2026-10'])
    expect(seleccionarMeses(serie, 3, true).map((x) => x.mes)).toEqual(['2026-08', '2026-09', '2026-10'])
    expect(seleccionarMeses(serie, 6).map((x) => x.mes)).toEqual(['2026-06', '2026-08', '2026-10'])
  })

  it('formatea variaciones', () => {
    expect(pctTexto(87.5)).toBe('+87,5 %')
    expect(pctTexto(-12)).toBe('-12 %')
    expect(pctTexto(null)).toBe('—')
  })

  it('agrupa la dona: 5 mayores y "Otras"', () => {
    const cats = [50, 20, 10, 8, 5, 4, 3].map((p, i) => ({ categoria: `C${i}`, monto: p * 1000, pct: p }))
    const seg = segmentosDona(cats)
    expect(seg).toHaveLength(6)
    expect(seg[5]).toEqual({ nombre: 'Otras', monto: 7000, pct: 7 })
  })
})

describe('GraficoTendencia', () => {
  const m = (mes, ingresos, gastos) => ({ mes, ingresos, gastos, ahorro: ingresos - gastos, num_movimientos: ingresos || gastos ? 3 : 0 })

  it('estado vacío amable cuando no hay movimientos', () => {
    render(<GraficoTendencia meses={[m('2026-09', 0, 0), m('2026-10', 0, 0)]} />)
    expect(screen.getByText(/Aún no hay movimientos/)).toBeInTheDocument()
  })

  it('muestra valores abreviados y avisa que con un solo mes no hay tendencia', () => {
    render(<GraficoTendencia meses={[m('2026-08', 0, 0), m('2026-09', 0, 0), m('2026-10', 1_234_567, 450_000)]} />)
    expect(screen.getByText('$1,2M')).toBeInTheDocument()
    expect(screen.getByText('$450k')).toBeInTheDocument()
    expect(screen.getByText(/Solo hay un mes con datos/)).toBeInTheDocument()
    // un mes con datos: solo "Oct" en el eje (los vacíos se saltan)
    expect(screen.queryByText('Ago')).not.toBeInTheDocument()
  })

  it('opción de mostrar meses sin datos, tabla accesible y tooltip al tocar', async () => {
    render(<GraficoTendencia meses={[m('2026-08', 0, 0), m('2026-09', 800_000, 600_000), m('2026-10', 1_000_000, 700_000)]} />)
    expect(screen.queryByText('Ago')).not.toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('Mostrar meses sin datos'))
    expect(screen.getByText('Ago')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /octubre de 2026: ingresos/i }))
    expect(screen.getByText(/Ahorro\s*\$\s*300\.000/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Ver tabla' }))
    const tabla = screen.getByRole('table')
    expect(within(tabla).getByText('septiembre de 2026')).toBeInTheDocument()
    expect(within(tabla).getAllByRole('row')).toHaveLength(4) // encabezado + 3 meses
  })
})

describe('SelectorPeriodo', () => {
  it('el rango personalizado solo se emite cuando es válido', async () => {
    const onChange = vi.fn()
    const { rerender } = render(<SelectorPeriodo valor={{ periodo: 'este_mes' }} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Personalizado' }))
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ periodo: 'rango' }))

    rerender(<SelectorPeriodo valor={{ periodo: 'rango', desde: '2026-10-01', hasta: '2026-10-05' }} onChange={onChange} />)
    onChange.mockClear()
    const [desde, hasta] = document.querySelectorAll('input[type="date"]')
    expect(desde).toBeTruthy()
    expect(hasta).toBeTruthy()
  })
})

const INFORME = {
  periodo: 'este_mes', etiqueta: 'octubre de 2026', hay_datos: true, total: 200_000, ingresos: 1_000_000, ahorro: 800_000,
  total_anterior: 100_000, variacion_pct: 100, anterior: { etiqueta: 'septiembre de 2026' },
  categorias: [
    { categoria: 'Comida', monto: 150_000, pct: 75, num: 2, anterior: 80_000, variacion_pct: 87.5 },
    { categoria: 'Transporte', monto: 50_000, pct: 25, num: 1, anterior: 20_000, variacion_pct: 150 },
  ],
  comercios: [{ nombre: 'Éxito', monto: 150_000, num: 2 }],
}

describe('Informe "En qué gasto"', () => {
  beforeEach(() => {
    api.informeGasto = vi.fn().mockResolvedValue(INFORME)
    api.informeMovimientos = vi.fn().mockResolvedValue({
      movimientos: [{ id: 'm1', fecha: '2026-10-02T12:00:00', descripcion: 'Éxito', monto: 100_000, categoria: 'Comida' }],
    })
  })

  it('muestra total, % por categoría, comparación y comercios; tocar una categoría lista sus movimientos', async () => {
    render(<MemoryRouter><Informe /></MemoryRouter>)
    expect(await screen.findByText(/Gastaste en octubre de 2026/)).toBeInTheDocument()
    expect(screen.getByText('+100 %')).toBeInTheDocument()
    expect(screen.getByText(/frente a septiembre de 2026/)).toBeInTheDocument()
    expect(screen.getAllByText('75 %').length).toBeGreaterThan(0)
    expect(screen.getByText('Dónde más gastas')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Comida/ }))
    expect(api.informeMovimientos).toHaveBeenCalledWith(expect.objectContaining({ categoria: 'Comida', periodo: 'este_mes' }))
    const lista = await screen.findByRole('list', { name: 'Movimientos de Comida' })
    expect(within(lista).getByText('Éxito')).toBeInTheDocument()
  })

  it('periodo personalizado manda desde y hasta al backend', async () => {
    render(<MemoryRouter><Informe /></MemoryRouter>)
    await screen.findByText(/Gastaste en/)
    await userEvent.click(screen.getByRole('button', { name: 'Personalizado' }))
    await waitFor(() =>
      expect(api.informeGasto).toHaveBeenLastCalledWith(expect.objectContaining({ periodo: 'rango', desde: expect.any(String), hasta: expect.any(String) }))
    )
  })

  it('sin datos en el periodo ofrece el último mes con gastos', async () => {
    api.informeGasto = vi.fn()
      .mockResolvedValueOnce({ ...INFORME, hay_datos: false, categorias: [], comercios: [], total: 0, ultimo_mes_con_datos: '2026-07' })
      .mockResolvedValue({ ...INFORME, etiqueta: 'julio de 2026' })
    render(<MemoryRouter><Informe /></MemoryRouter>)
    await userEvent.click(await screen.findByRole('button', { name: /Ver julio de 2026/ }))
    await waitFor(() => expect(api.informeGasto).toHaveBeenLastCalledWith({ periodo: 'mes', mes: '2026-07' }))
  })
})

describe('Mi resumen (Wrapped) por meses con datos', () => {
  it('abre en el último mes con datos si el actual está vacío y permite navegar', async () => {
    api.informeMeses = vi.fn().mockResolvedValue({
      meses: [{ mes: '2026-06' }, { mes: '2026-07' }], ultimo_con_datos: '2026-07',
    })
    api.wrapped = vi.fn().mockResolvedValue({
      mes: '2026-07', gasto_total: 500_000, ingresos: 900_000, ahorro: 400_000, tasa_ahorro: 44.4,
      categoria_top: { categoria: 'Mercado', monto: 300_000 }, mejor_racha: 2, num_movimientos: 8,
      gasto_mes_anterior: 0, variacion_gasto_pct: null,
    })
    render(<DialogosProvider><MemoryRouter><Wrapped /></MemoryRouter></DialogosProvider>)
    await waitFor(() => expect(api.wrapped).toHaveBeenCalledWith('2026-07'))
    expect(screen.getByLabelText('Elegir mes')).toHaveValue('2026-07')
    await userEvent.click(screen.getByRole('button', { name: 'Mes anterior' }))
    await waitFor(() => expect(api.wrapped).toHaveBeenCalledWith('2026-06'))
  })
})
