// Dos compras idénticas el mismo día comparten huella: claves únicas y conteo por filas.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  obtenerReviewExtracto: vi.fn(),
  importarFaltantes: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Nu' }], recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Otros'], iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import Conciliacion from '../screens/Conciliacion'
import { clavesFilas, filasAImportar } from '../lib/conciliacionClaves'

const review = [
  { fingerprint: 'x', fecha: '2026-10-03', descripcion: 'TIENDA D1', monto: 5000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Comida' },
  { fingerprint: 'x', fecha: '2026-10-03', descripcion: 'TIENDA D1', monto: 5000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Comida' },
  { fingerprint: 'y', fecha: '2026-10-02', descripcion: 'Netflix', monto: 33000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Otros' },
]

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

describe('claves de filas', () => {
  it('huellas repetidas obtienen claves distintas y estables', () => {
    expect(clavesFilas(review)).toEqual(['x#0', 'x#1', 'y#0'])
    expect(clavesFilas(review)).toEqual(clavesFilas(review))
  })
  it('cuenta filas, no huellas', () => {
    expect(filasAImportar(review, new Set(['x', 'y']))).toBe(3)
    expect(filasAImportar(review, new Set(['y']))).toBe(1)
  })
})

describe('Conciliacion con filas idénticas', () => {
  it('sin warning de claves repetidas, ambas filas visibles y el botón cuenta 3', async () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    api.obtenerReviewExtracto.mockResolvedValue({ ok: true, historial_id: 'h1', review, resumen: {} })
    api.importarFaltantes.mockResolvedValue({ importados: 3 })
    render(
      <DialogosProvider>
        <MemoryRouter initialEntries={[{ pathname: '/', state: { historialId: 'h1' } }]}>
          <Conciliacion />
        </MemoryRouter>
      </DialogosProvider>
    )
    expect(await screen.findAllByText('TIENDA D1')).toHaveLength(2)
    const boton = screen.getByRole('button', { name: /Importar \(3\)/ })
    expect(boton).toBeInTheDocument()
    const avisosClave = err.mock.calls.filter((c) => String(c[0]).includes('same key'))
    expect(avisosClave).toHaveLength(0)

    await userEvent.click(boton)
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalled())
    // huella 'x' va una sola vez (el servidor importa las dos filas idénticas)
    expect(api.importarFaltantes.mock.calls[0][1].sort()).toEqual(['x', 'y'])
    err.mockRestore()
  })
})
