import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import GraficoMeses from '../components/GraficoMeses'
import EvolucionCategoria from '../components/EvolucionCategoria'
import { limpiarCacheEvolucion } from '../lib/useEvolucionCategorias'
import { abreviarEje, fraseEvolucion } from '../lib/graficos'

const fmt = (v) => `$${Math.round(v).toLocaleString('es-CO')}`
const MESES = [
  { mes: '2026-08', etiqueta: 'ago', etiqueta_larga: 'agosto de 2026', ingresos: 3_000_000, gastos: 2_000_000, balance: 1_000_000, tasa_ahorro: 33.3, variacion: null },
  { mes: '2026-09', etiqueta: 'sep', etiqueta_larga: 'septiembre de 2026', ingresos: 3_000_000, gastos: 2_400_000, balance: 600_000, tasa_ahorro: 20, variacion: { gastos_pct: 20 } },
  { mes: '2026-10', etiqueta: 'oct', etiqueta_larga: 'octubre de 2026', ingresos: 3_200_000, gastos: 1_000_000, balance: 2_200_000, tasa_ahorro: 68.8, variacion: { gastos_pct: -58.3 } },
]

describe('GraficoMeses', () => {
  it('teclado: las flechas muestran el mes, Enter lo selecciona y Esc limpia', async () => {
    const user = userEvent.setup()
    const onSel = vi.fn()
    render(<GraficoMeses meses={MESES} fmt={fmt} onSeleccion={onSel} />)
    const lienzo = screen.getByRole('group', { name: /Gráfico de ingresos/ })
    expect(screen.queryByTestId('lectura')).toBeNull()
    lienzo.focus()
    await user.keyboard('{ArrowRight}')
    expect(within(screen.getByTestId('lectura')).getByText('agosto de 2026')).toBeInTheDocument()
    await user.keyboard('{ArrowRight}')
    const tip = screen.getByTestId('lectura')
    expect(within(tip).getByText('septiembre de 2026')).toBeInTheDocument()
    expect(within(tip).getByText('20 %')).toBeInTheDocument()
    expect(within(tip).getByText(/Gastos vs mes anterior: ↑ 20 %/)).toBeInTheDocument()
    await user.keyboard('{Enter}')
    expect(onSel).toHaveBeenCalledWith('2026-09')
    await user.keyboard('{Escape}')
    expect(screen.queryByTestId('lectura')).toBeNull()
  })

  it('la selección atenúa los demás meses y permite volver al periodo completo', async () => {
    const user = userEvent.setup()
    const onSel = vi.fn()
    const { container } = render(<GraficoMeses meses={MESES} fmt={fmt} seleccion="2026-10" onSeleccion={onSel} />)
    expect(container.querySelector('[data-mes="2026-10"]').dataset.seleccionado).toBe('true')
    expect(container.querySelector('[data-mes="2026-08"]').getAttribute('opacity')).toBe('0.4')
    await user.click(screen.getByRole('button', { name: 'Ver el periodo completo' }))
    expect(onSel).toHaveBeenCalledWith(null)
  })

  it('la leyenda oculta y muestra series; hay tabla para lectores de pantalla', async () => {
    const user = userEvent.setup()
    const { container } = render(<GraficoMeses meses={MESES} fmt={fmt} />)
    expect(container.querySelectorAll('path.gr-barra').length).toBe(6)
    const gastos = screen.getByRole('button', { name: 'Gastos' })
    expect(gastos).toHaveAttribute('aria-pressed', 'true')
    await user.click(gastos)
    expect(gastos).toHaveAttribute('aria-pressed', 'false')
    expect(container.querySelectorAll('path.gr-barra').length).toBe(3)
    await user.click(gastos)
    expect(container.querySelectorAll('path.gr-barra').length).toBe(6)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('img').getAttribute('aria-label')).toMatch(/octubre de 2026, ingresos \$3\.200\.000/)
  })
})

describe('utilidades de gráficos', () => {
  it('abrevia los ejes y arma la frase de evolución', () => {
    expect(abreviarEje(1_200_000)).toBe('$1,2 M')
    expect(abreviarEje(85_000)).toBe('$85 k')
    expect(abreviarEje(0)).toBe('$0')
    expect(fraseEvolucion('Transporte', { vs_promedio_pct: 18.4 }, 'septiembre')).toBe('En septiembre, Transporte subió 18 % frente a su promedio.')
    expect(fraseEvolucion('Mercado', { vs_promedio_pct: -25 })).toBe('Mercado bajó 25 % frente a su promedio.')
    expect(fraseEvolucion('Ocio', { vs_promedio_pct: 1 })).toBe('Ocio se mantuvo en su promedio.')
    expect(fraseEvolucion('Ocio', null)).toMatch(/Todavía no hay/)
  })
})

const serie = (valores, prom) => ({
  valores, total: valores.reduce((a, b) => a + b, 0), promedio: prom,
  vs_anterior_pct: valores.map((v, i) => (i ? Math.round(((v - valores[i - 1]) / valores[i - 1]) * 100) : null)),
  vs_promedio_pct: valores.map((v) => Math.round(((v - prom) / prom) * 100)),
  resumen: { mes: '2026-09', indice: 1, valor: valores[1], vs_promedio_pct: Math.round(((valores[1] - prom) / prom) * 100), vs_anterior_pct: 0 },
})
const EVO = {
  meses: [
    { mes: '2026-08', etiqueta: 'ago', etiqueta_larga: 'agosto de 2026', parcial: false },
    { mes: '2026-09', etiqueta: 'sep', etiqueta_larga: 'septiembre de 2026', parcial: false },
    { mes: '2026-10', etiqueta: 'oct', etiqueta_larga: 'octubre de 2026', parcial: true },
  ],
  total_mensual: [300, 400, 100],
  serie_total: serie([300_000, 400_000, 100_000], 350_000),
  categorias: [
    { categoria: 'Transporte', ...serie([100_000, 130_000, 40_000], 110_000) },
    { categoria: 'Mercado', ...serie([200_000, 270_000, 60_000], 235_000) },
  ],
  hay_datos: true,
}

describe('EvolucionCategoria', () => {
  beforeEach(() => {
    limpiarCacheEvolucion()
    api.evolucionCategorias = vi.fn(async (p) => (p.categoria
      ? {
          ...EVO,
          categoria: p.categoria,
          tiene_subcategorias: true,
          subcategorias: [
            { subcategoria: 'Taxi', ...serie([60_000, 90_000, 30_000], 75_000) },
            { subcategoria: null, ...serie([40_000, 40_000, 10_000], 40_000) },
          ],
        }
      : EVO))
  })

  it('chips con las categorías, frase de resumen y cambio de categoría', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><EvolucionCategoria fmt={fmt} /></MemoryRouter>)
    const chips = await screen.findByRole('group', { name: 'Categoría' })
    expect(within(chips).getAllByRole('button').map((b) => b.textContent)).toEqual(['Todas', 'Transporte', 'Mercado'])
    expect(screen.getByTestId('frase-evolucion').textContent).toBe('En septiembre, Tu gasto total subió 14 % frente a su promedio.')
    await user.click(within(chips).getByRole('button', { name: 'Transporte' }))
    expect(screen.getByTestId('frase-evolucion').textContent).toBe('En septiembre, Transporte subió 18 % frente a su promedio.')
    expect(await screen.findByRole('list', { name: 'Subcategorías' })).toHaveTextContent('Sin subcategoría')
    await user.click(screen.getByRole('button', { name: '12 meses' }))
    expect(api.evolucionCategorias).toHaveBeenCalledWith({ meses: 12 })
  })

  it('el teclado muestra variación frente al mes anterior y a su promedio', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><EvolucionCategoria fmt={fmt} /></MemoryRouter>)
    await screen.findByRole('group', { name: 'Categoría' })
    screen.getByRole('group', { name: /Gráfico del gasto mensual/ }).focus()
    await user.keyboard('{ArrowRight}{ArrowRight}')
    const tip = screen.getByTestId('lectura')
    expect(within(tip).getByText('septiembre de 2026')).toBeInTheDocument()
    expect(within(tip).getByText('Vs su promedio').closest('div').querySelector('dd').textContent).toBe('↑ 14 %')
    expect(within(tip).getByText('Vs mes anterior').closest('div').querySelector('dd').textContent).toBe('↑ 33 %')
  })
})
