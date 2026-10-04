// Guía de "un atajo, dos automatizaciones", prueba de registro rápido y las tres
// listas de la revisión de conciliación.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
import ConectarDispositivo, { ATAJO_ICLOUD_URL } from '../screens/ConectarDispositivo'
import Conciliacion, { resumenCompletados } from '../screens/Conciliacion'

const montar = (ui, estado) =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[{ pathname: '/', state: estado }]}>{ui}</MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

describe('guía de los dos atajos', () => {
  it('explica dos atajos con sus automatizaciones y conserva el aviso "llega pronto"', () => {
    expect(ATAJO_ICLOUD_URL).toBe('')
    api.apiKey.mockResolvedValue({ api_key: 'k' })
    montar(<ConectarDispositivo />)
    expect(screen.getByText('Dos atajos, dos tipos de automatización')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Apple Pay y el cierre de cualquier app/ })).toBeInTheDocument()
    expect(screen.getByText(/Automatización 1: pagos con Apple Pay/)).toBeInTheDocument()
    expect(screen.getByText(/Automatización 2: cierre de una app/)).toBeInTheDocument()
    expect(screen.getByText(/Se cierra/, { selector: 'b' })).toBeInTheDocument()
    expect(screen.getAllByText(/¿Hiciste algún movimiento\?/).length).toBeGreaterThan(0)
    expect(screen.getByText(/llega pronto/)).toBeInTheDocument()
  })

  it('"Probar registro rápido" crea un movimiento por confirmar con fuente cierre_app', async () => {
    api.apiKey.mockResolvedValue({ api_key: 'cm_k' })
    api.registroRapidoDePrueba.mockResolvedValue({ id: 'r1', mensaje: 'Gasto de $1.000 en Movimiento en Nequi' })
    api.movimientosPorConfirmar.mockResolvedValue([{ id: 'r1' }])
    montar(<ConectarDispositivo />)
    const boton = screen.getByRole('button', { name: /Probar registro rápido/ })
    await waitFor(() => expect(boton).not.toBeDisabled())
    await userEvent.click(boton)
    expect(await screen.findByText('¡Funciona el registro rápido!')).toBeInTheDocument()
    expect(api.registroRapidoDePrueba).toHaveBeenCalledWith('cm_k')
  })
})

describe('revisión de conciliación con tres listas', () => {
  const review = [
    { fingerprint: 'a', fecha: '2026-10-03', descripcion: 'RESTAURANTE EL CORRAL', monto: 25000, tipo: 'expense',
      estado: 'completado', match_id: 'm1', categoria_sugerida: 'Comida', descripcion_registrada: 'mi almuerzo', monto_registrado: 25000 },
    { fingerprint: 'b', fecha: '2026-10-03', descripcion: 'Netflix', monto: 33000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Otros' },
    { fingerprint: 'sobrante-m2', fecha: '2026-10-03 10:00', descripcion: 'Movimiento en Nequi', monto: 9000, tipo: 'expense', estado: 'sobrante', match_id: 'm2' },
    { fingerprint: 'd', fecha: '2026-10-02', descripcion: 'Spotify', monto: 16900, tipo: 'expense', estado: 'exacto' },
  ]

  it('resumen con singular y plural', () => {
    expect(resumenCompletados(0)).toBeNull()
    expect(resumenCompletados(1)).toBe('Completé 1 movimiento con tu extracto')
    expect(resumenCompletados(3)).toBe('Completé 3 movimientos con tu extracto')
  })

  it('muestra completados, faltantes y sobrantes en secciones claras', async () => {
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h1', exactos: 1, aproximados: 0, faltantes: 1, completados: 1, sobrantes: 1,
      total_movimientos: 3, descartados: 0, review,
    })
    montar(<Conciliacion />, { historialId: 'h1' })
    expect(await screen.findByText('Completé 1 movimiento con tu extracto')).toBeInTheDocument()
    const completados = screen.getByRole('region', { name: 'Completados con el banco' })
    expect(within(completados).getByText('RESTAURANTE EL CORRAL')).toBeInTheDocument()
    expect(within(completados).getByText(/Tú anotaste: mi almuerzo/)).toBeInTheDocument()
    const faltan = screen.getByRole('region', { name: 'Faltan en CuadraMe' })
    expect(within(faltan).getByText('Netflix')).toBeInTheDocument()
    const sobran = screen.getByRole('region', { name: 'Registrados que no aparecen en el extracto' })
    expect(within(sobran).getByText('Movimiento en Nequi')).toBeInTheDocument()
    expect(within(sobran).queryByText('Netflix')).toBeNull()
  })

  it('avisa si el monto registrado difiere del banco', async () => {
    const r = [{ ...review[0], monto_registrado: 24000 }]
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h2', exactos: 0, aproximados: 0, faltantes: 0, completados: 1, sobrantes: 0,
      total_movimientos: 1, descartados: 0, review: r,
    })
    montar(<Conciliacion />, { historialId: 'h2' })
    expect(await screen.findByText(/el banco dice/)).toBeInTheDocument()
  })
})
