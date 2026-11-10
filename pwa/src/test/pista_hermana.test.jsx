// «Tienes algo igual en tu otra cuenta»: aviso en la línea que falta, con botón para pasarlo y sin importar dos veces.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  obtenerReviewExtracto: vi.fn(),
  editarMovimiento: vi.fn(),
  importarFaltantes: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Nequi Principal' }, { id: 'c2', nombre: 'Nequi Bolsillo' }], recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Servicios', 'Otros'], iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import SubidaMultiple from '../components/SubidaMultiple'

const montar = (ui) => render(<DialogosProvider><MemoryRouter>{ui}</MemoryRouter></DialogosProvider>)

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

describe('pista de cuenta hermana', () => {
  it('avisa y «Pasarlo a esta cuenta» mueve el movimiento y quita la línea de lo nuevo', async () => {
    api.editarMovimiento.mockResolvedValue({})
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h1', cuenta_id: 'c2', exactos: 0, aproximados: 0, faltantes: 1, completados: 0, sobrantes: 0,
      total_movimientos: 1, descartados: 0,
      review: [{
        fingerprint: 'f1', fecha: '2026-10-03', descripcion: 'PAGO LUZ', monto: 70000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Servicios',
        pista_hermana: {
          movimiento_id: 'm1', cuenta_id: 'c1', cuenta_nombre: 'Nequi Principal',
          mensaje: 'Tienes algo igual en tu otra cuenta de Nequi Principal: «Pago luz».',
          accion: { etiqueta: 'Pasarlo a esta cuenta', movimiento_id: 'm1', cuenta_id: 'c2' },
        },
      }],
    })
    montar(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} />)
    expect(await screen.findByText(/Tienes algo igual en tu otra cuenta de Nequi Principal/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Pasarlo a esta cuenta' }))
    await waitFor(() => expect(api.editarMovimiento).toHaveBeenCalledWith('m1', { cuenta_id: 'c2' }))
    expect(await screen.findByText(/Esa línea ya no se importa/)).toBeInTheDocument()
    expect(screen.queryByTestId('pista-hermana')).toBeNull()
  })
})
