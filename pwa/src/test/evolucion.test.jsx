import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import GraficoEvolucion from '../components/GraficoEvolucion'
import { lecturaEvolucion, repartirEtiquetas, resumenAria, tramos } from '../lib/evolucion'

const fmt = (v) => `$${Math.round(v).toLocaleString('es-CO')}`
const P = (clave, larga, ing, gas, extra = {}) => ({
  clave, etiqueta: larga.slice(0, 3), etiqueta_larga: larga, desde: `${clave}-01`, hasta: `${clave}-28`,
  ingresos: ing, gastos: gas, ahorro: ing === null ? null : ing - gas, acumulado: 0, con_datos: ing !== null, en_curso: false, ...extra,
})
const DATOS = {
  agrupar: 'mes', meses: 6, hay_datos: true, meses_con_datos: 3, inicio: null,
  puntos: [
    P('2026-08', 'agosto de 2026', 3_000_000, 1_000_000),
    P('2026-09', 'septiembre de 2026', 3_000_000, 1_120_000),
    P('2026-10', 'octubre de 2026', 500_000, 200_000, { en_curso: true }),
  ],
}

describe('lecturaEvolucion', () => {
  it('nombra el mejor mes y compara gastos sin culpar', () => {
    const f = lecturaEvolucion(DATOS.puntos, 'mes', fmt)
    expect(f[0]).toContain('Tu ahorro fue mayor en agosto')
    expect(f[1]).toBe('En septiembre gastaste 12 % más que en agosto.')
    expect(f[2]).toContain('Octubre sigue en curso')
  })
  it('no dice nada con menos de 2 periodos con datos', () => {
    expect(lecturaEvolucion([DATOS.puntos[0]], 'mes', fmt)).toEqual([])
  })
  it('sin ahorro usa un tono amable', () => {
    const f = lecturaEvolucion([P('2026-08', 'agosto de 2026', 100, 300), P('2026-09', 'septiembre de 2026', 100, 300)], 'mes', fmt)
    expect(f[0]).toMatch(/Pasa;/)
  })
  it('no compara a través de un hueco', () => {
    const f = lecturaEvolucion([P('2026-07', 'julio de 2026', 100, 10), P('2026-08', 'agosto de 2026', null, null), P('2026-09', 'septiembre de 2026', 100, 90)], 'mes', fmt)
    expect(f.join(' ')).not.toMatch(/más que/)
  })
})

describe('utilidades', () => {
  it('tramos corta la línea en los huecos', () => {
    const p = [P('a', 'a', 1, 1), P('b', 'b', null, null), P('c', 'c', 1, 1), P('d', 'd', 1, 1)]
    expect(tramos(p, 'ahorro').map((t) => t.length)).toEqual([1, 2])
  })
  it('resumen para lectores de pantalla incluye huecos', () => {
    expect(resumenAria([P('a', 'julio', 5, 2), P('b', 'agosto', null, null)], 'mes', fmt)).toMatch(/julio: ingresos \$5, gastos \$2, ahorro \$3; agosto: sin movimientos/)
  })
  it('repartirEtiquetas separa las que se pisan', () => {
    const r = repartirEtiquetas([{ k: 'a', y: 10 }, { k: 'b', y: 11 }])
    expect(r[1].y - r[0].y).toBeGreaterThanOrEqual(11)
  })
})

describe('GraficoEvolucion', () => {
  beforeEach(() => {
    api.evolucion = vi.fn().mockResolvedValue(DATOS)
  })

  it('pide 6 meses por mes y muestra la gráfica con etiqueta accesible y lectura', async () => {
    render(<GraficoEvolucion fmt={fmt} />)
    expect(await screen.findByRole('img', { name: /Evolución de ingresos, gastos y ahorro por mes/ })).toBeInTheDocument()
    expect(api.evolucion).toHaveBeenCalledWith({ agrupar: 'mes', meses: 6 })
    expect(screen.getByTestId('lectura-evolucion')).toHaveTextContent('Tu ahorro fue mayor en agosto')
    expect(screen.getByText('en curso')).toBeInTheDocument()
  })

  it('cambia rango y vista pidiendo al servidor', async () => {
    const u = userEvent.setup()
    render(<GraficoEvolucion fmt={fmt} />)
    await screen.findByRole('img')
    await u.click(screen.getByRole('button', { name: 'Todo' }))
    await waitFor(() => expect(api.evolucion).toHaveBeenLastCalledWith({ agrupar: 'mes', meses: 0 }))
    await u.click(screen.getByRole('button', { name: 'Por semana' }))
    await waitFor(() => expect(api.evolucion).toHaveBeenLastCalledWith({ agrupar: 'semana', meses: 0 }))
  })

  it('al tocar un mes muestra sus tres números', async () => {
    const u = userEvent.setup()
    render(<GraficoEvolucion fmt={fmt} />)
    await screen.findByRole('img')
    await u.click(screen.getByTestId('punto-2026-08'))
    const det = screen.getByTestId('detalle-punto')
    expect(det).toHaveTextContent('agosto de 2026')
    expect(det).toHaveTextContent('$3.000.000')
    expect(det).toHaveTextContent('$1.000.000')
    expect(det).toHaveTextContent('$2.000.000')
  })

  it('Ver como tabla muestra los números y los huecos como «Sin movimientos»', async () => {
    api.evolucion = vi.fn().mockResolvedValue({ ...DATOS, puntos: [DATOS.puntos[0], P('2026-09', 'septiembre de 2026', null, null), DATOS.puntos[2]] })
    const u = userEvent.setup()
    render(<GraficoEvolucion fmt={fmt} />)
    await screen.findByRole('img')
    await u.click(screen.getByRole('button', { name: 'Ver como tabla' }))
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('Sin movimientos')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ver gráfica' })).toBeInTheDocument()
  })

  it('estado vacío amable con menos de 2 meses', async () => {
    api.evolucion = vi.fn().mockResolvedValue({ ...DATOS, meses_con_datos: 1 })
    render(<GraficoEvolucion fmt={fmt} />)
    expect(await screen.findByText(/al menos 2 meses verás tu evolución/)).toBeInTheDocument()
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('error con reintento', async () => {
    api.evolucion = vi.fn().mockRejectedValueOnce(new Error('x')).mockResolvedValue(DATOS)
    const u = userEvent.setup()
    render(<GraficoEvolucion fmt={fmt} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('No pudimos cargar')
    await u.click(screen.getByRole('button', { name: /Reintentar/ }))
    expect(await screen.findByRole('img')).toBeInTheDocument()
  })
})
