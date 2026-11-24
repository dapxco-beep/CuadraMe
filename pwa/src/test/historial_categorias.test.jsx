import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../lib/api'
import { limpiarCacheEvolucion } from '../lib/useEvolucionCategorias'
import HistorialCategorias from '../components/HistorialCategorias'

vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ iconoDe: () => '🛒', nombres: [], categorias: [] }),
}))

const serie = (valores) => ({
  valores, total: valores.reduce((a, b) => a + b, 0), promedio: 1000,
  vs_anterior_pct: valores.map(() => null), vs_promedio_pct: valores.map(() => null), resumen: null,
})
const cats = Array.from({ length: 10 }, (_, i) => ({ categoria: `Cat ${i + 1}`, ...serie([1000 * (i + 1), 0, 500]) }))
const DATOS = {
  hay_datos: true,
  meses: [
    { mes: '2026-09', etiqueta: 'sep', etiqueta_larga: 'septiembre de 2026', parcial: false },
    { mes: '2026-10', etiqueta: 'oct', etiqueta_larga: 'octubre de 2026', parcial: false },
    { mes: '2026-11', etiqueta: 'nov', etiqueta_larga: 'noviembre de 2026', parcial: true },
  ],
  total_mensual: [55000, 0, 5000],
  serie_total: serie([55000, 0, 5000]),
  categorias: cats,
}
const fmt = (n) => `$${n}`

describe('Historial por categoría', () => {
  beforeEach(() => {
    limpiarCacheEvolucion()
    api.evolucionCategorias = vi.fn().mockResolvedValue(DATOS)
  })

  it('muestra una fila por categoría, con «Ver todas» cuando son más de 8', async () => {
    render(<HistorialCategorias fmt={fmt} />)
    const tabla = await screen.findByRole('table')
    expect(within(tabla).getAllByRole('row').length).toBe(1 + 8 + 1) // encabezado + 8 + pie
    await userEvent.click(screen.getByRole('button', { name: /Ver las 10 categorías/ }))
    expect(within(tabla).getAllByRole('row').length).toBe(1 + 10 + 1)
    expect(screen.getByText('Cat 10')).toBeInTheDocument()
  })

  it('pide 12 meses al cambiar el selector', async () => {
    render(<HistorialCategorias fmt={fmt} />)
    await screen.findByRole('table')
    await userEvent.click(screen.getByRole('button', { name: '12 meses' }))
    await waitFor(() => expect(api.evolucionCategorias).toHaveBeenLastCalledWith({ meses: 12 }))
  })
})
