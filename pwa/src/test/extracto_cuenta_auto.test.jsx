// Extracto de otra cuenta del mismo banco (tarjeta vs ahorros): se pasa solo, con «Deshacer».
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  procesarExtracto: vi.fn(),
  obtenerReviewExtracto: vi.fn(),
  cambiarCuentaExtracto: vi.fn(),
  importarFaltantes: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({
    cuentas: [{ id: 'c1', nombre: 'Nu Ahorros', icono: '💜' }, { id: 'c2', nombre: 'Nu Tarjeta', icono: '💳' }],
    recargar: vi.fn(),
  }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Otros'], iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import SubidaMultiple from '../components/SubidaMultiple'

const montar = (ui) => render(<DialogosProvider><MemoryRouter>{ui}</MemoryRouter></DialogosProvider>)
const REVIEW = [{ fingerprint: 'fp1', fecha: '2026-09-03', descripcion: 'CAFE', monto: 9000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Otros' }]
const LECTURA = { ok: true, historial_id: 'h1', banco_detectado: 'nu', total_movimientos: 1, periodo_desde: '2026-09-01', periodo_hasta: '2026-09-30', review: REVIEW }

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

async function subir() {
  const pdf = new File(['%PDF-1.4'], 'sep.pdf', { type: 'application/pdf' })
  montar(<SubidaMultiple archivosIniciales={[pdf]} cuentaInicial="c1" onCancelar={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: /Procesar/ }))
  await screen.findByText('Listo')
  await userEvent.click(await screen.findByRole('button', { name: /Revisar/ }))
}

describe('cuenta equivocada del mismo banco', () => {
  it('la cambia sola, lo dice y deja deshacer', async () => {
    api.procesarExtracto.mockResolvedValue({ ...LECTURA, aviso_cuenta: '¿Será «Nu Tarjeta»?', aviso_cuenta_id: 'c2' })
    api.cambiarCuentaExtracto.mockResolvedValue({ ok: true })
    api.obtenerReviewExtracto.mockResolvedValue({ ...LECTURA, cuenta_id: 'c2' })
    await subir()
    expect(await screen.findByText(/Lo pasé a Nu Tarjeta/)).toBeInTheDocument()
    expect(api.cambiarCuentaExtracto).toHaveBeenCalledWith('h1', 'c2')
    expect(screen.queryByTestId('aviso-cuenta')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }))
    await waitFor(() => expect(api.cambiarCuentaExtracto).toHaveBeenLastCalledWith('h1', 'c1'))
    await waitFor(() => expect(screen.queryByText(/Lo pasé a/)).toBeNull())
  })

  it('si no se pudo pasar sola, deja el aviso con botón «Cambiar»', async () => {
    api.procesarExtracto.mockResolvedValue({ ...LECTURA, aviso_cuenta: '¿Será «Nu Tarjeta»?', aviso_cuenta_id: 'c2' })
    api.cambiarCuentaExtracto.mockRejectedValueOnce(new Error('falló')).mockResolvedValue({ ok: true })
    api.obtenerReviewExtracto.mockResolvedValue({ ...LECTURA, cuenta_id: 'c2' })
    await subir()
    expect(await screen.findByTestId('aviso-cuenta')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar' }))
    expect(await screen.findByText(/Lo pasé a Nu Tarjeta/)).toBeInTheDocument()
  })
})
