// Guía de "un atajo, dos automatizaciones", prueba de registro rápido y las tres
// listas de la revisión de conciliación.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  apiKey: vi.fn(),
  pagoDePrueba: vi.fn(),
  registroRapidoDePrueba: vi.fn(),
  movimientosPorConfirmar: vi.fn(),
  obtenerReviewExtracto: vi.fn(),
  procesarExtracto: vi.fn(),
  importarFaltantes: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Nequi' }], recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Otros'], iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import SubidaMultiple from '../components/SubidaMultiple'

const montar = (ui, estado) =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[{ pathname: '/', state: estado }]}>{ui}</MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

describe('revisión de conciliación con tres listas', () => {
  const review = [
    { fingerprint: 'a', fecha: '2026-10-03', descripcion: 'RESTAURANTE EL CORRAL', monto: 25000, tipo: 'expense',
      estado: 'completado', match_id: 'm1', categoria_sugerida: 'Comida', descripcion_registrada: 'mi almuerzo', monto_registrado: 25000 },
    { fingerprint: 'b', fecha: '2026-10-03', descripcion: 'Netflix', monto: 33000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Otros' },
    { fingerprint: 'sobrante-m2', fecha: '2026-10-03 10:00', descripcion: 'Movimiento en Nequi', monto: 9000, tipo: 'expense', estado: 'sobrante', match_id: 'm2' },
    { fingerprint: 'd', fecha: '2026-10-02', descripcion: 'Spotify', monto: 16900, tipo: 'expense', estado: 'exacto' },
  ]

  it('el resumen de completados usa singular y plural', async () => {
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h3', cuenta_id: 'c1', exactos: 0, aproximados: 0, faltantes: 0, completados: 2, sobrantes: 0,
      total_movimientos: 2, descartados: 0, review: [review[0], { ...review[0], fingerprint: 'z' }],
    })
    montar(<SubidaMultiple revisionInicial={{ historialId: 'h3' }} />)
    expect(await screen.findByText('Completé 2 movimientos con tu extracto')).toBeInTheDocument()
  })

  it('muestra completados, faltantes y sobrantes en la revisión consolidada', async () => {
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h1', cuenta_id: 'c1', exactos: 1, aproximados: 0, faltantes: 1, completados: 1, sobrantes: 1,
      total_movimientos: 3, descartados: 0, review,
    })
    montar(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} />)
    expect(await screen.findByText('Completé 1 movimiento con tu extracto')).toBeInTheDocument()
    expect(screen.getByText('Netflix')).toBeInTheDocument() // lo que falta
    const sobran = screen.getByText('1 registrado no aparece en el extracto').closest('details')
    expect(within(sobran).getByText(/Movimiento en Nequi/)).toBeInTheDocument()
    expect(within(sobran).queryByText(/Netflix/)).toBeNull()
  })

  it('avisa si el monto registrado difiere del banco', async () => {
    const r = [{ ...review[0], monto_registrado: 24000 }]
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h2', cuenta_id: 'c1', exactos: 0, aproximados: 0, faltantes: 0, completados: 1, sobrantes: 0,
      total_movimientos: 1, descartados: 0, review: r,
    })
    montar(<SubidaMultiple revisionInicial={{ historialId: 'h2' }} />)
    expect(await screen.findByText(/el banco dice/)).toBeInTheDocument()
  })

  it('avisa las líneas del PDF que no se pudieron leer', async () => {
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h4', cuenta_id: 'c1', exactos: 0, aproximados: 0, faltantes: 1, completados: 0, sobrantes: 0,
      total_movimientos: 1, descartados: 3, review: [review[1]],
    })
    montar(<SubidaMultiple revisionInicial={{ historialId: 'h4' }} />)
    expect(await screen.findByTestId('aviso-descartados')).toHaveTextContent('3 líneas no se pudieron leer con certeza')
  })
})
