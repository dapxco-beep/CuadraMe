import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [
  { id: 'n', nombre: 'Nequi', saldo: 485000, moneda: 'COP', tipo: 'ahorro', icono: '💜' },
  { id: 'u', nombre: 'Nu', saldo: 2500000, moneda: 'COP', tipo: 'ahorro', icono: '🟣' },
]
const MARCA = 'posible_traslado_propio'
const MOVS = [
  { id: 'e', cuenta_id: 'n', fecha: '2026-10-05T12:00:00', descripcion: 'Enviaste a Ana', categoria: 'Transferencias', tipo: 'expense', monto: 500000, fuente: 'importacion_archivo', notas: `Importado de n.csv · ${MARCA}` },
  { id: 'i', cuenta_id: 'u', fecha: '2026-10-05T12:00:00', descripcion: 'Recibiste de Ana', categoria: 'Transferencias', tipo: 'income', monto: 500000, fuente: 'importacion_archivo', notas: `Importado de u.csv · ${MARCA}` },
  { id: 't', cuenta_id: 'n', fecha: '2026-10-05T12:00:00', descripcion: 'Pago a Pepito', categoria: 'Transferencias', tipo: 'expense', monto: 15000, fuente: 'importacion_archivo', notas: 'Importado de n.csv' },
]

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ categorias: [], nombres: ['Otros'], cargando: false, recargar: vi.fn(), iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import DetalleMovimiento from '../screens/DetalleMovimiento'
import { ThemeProvider } from '../lib/ThemeContext'
import {
  candidatosContraparte, cambiosEsReal, cambiosMarcarTraslado, direccionDe, etiquetaTipo, signoDe,
} from '../lib/traslados'

function detalle(id) {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter initialEntries={[`/movimientos/${id}`]}>
          <Routes><Route path="/movimientos/:id" element={<DetalleMovimiento />} /></Routes>
        </MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    movimiento: vi.fn((id) => Promise.resolve(MOVS.find((m) => m.id === id))),
    movimientos: vi.fn().mockResolvedValue(MOVS),
    editarMovimiento: vi.fn((id, d) => Promise.resolve({ ...MOVS.find((m) => m.id === id), ...d })),
  })
})

describe('lib/traslados', () => {
  it('dirección y signo siguen al movimiento, también en las patas de un traslado de la app', () => {
    expect(signoDe(MOVS[0])).toBe('-')
    expect(signoDe(MOVS[1])).toBe('+')
    const pata = { tipo: 'transfer', fuente: 'transferencia_interna', notas: 'TRF:g:in', categoria: 'Transferencia' }
    expect(direccionDe(pata)).toBe('income')
    expect(etiquetaTipo(pata)).toBe('Traslado ↔ (entra)')
    expect(etiquetaTipo(MOVS[0])).toBe('Posible traslado ↔ (sale)')
    expect(etiquetaTipo(MOVS[2])).toBe('Gasto')
  })

  it('candidatos: dirección opuesta, mismo monto, otra cuenta, <= 2 días', () => {
    expect(candidatosContraparte(MOVS[0], MOVS).map((m) => m.id)).toEqual(['i'])
    const lejos = { ...MOVS[1], fecha: '2026-10-09T12:00:00' }
    expect(candidatosContraparte(MOVS[0], [lejos])).toEqual([])
  })

  it('"es real" quita la pista y deja la marca; "traslado" fija la categoría neutral', () => {
    expect(cambiosEsReal(MOVS[0]).notas).toBe('Importado de n.csv · no_es_traslado')
    expect(cambiosMarcarTraslado(MOVS[0])).toEqual({ categoria: 'Transferencia', notas: `Importado de n.csv · ${MARCA}` })
  })
})

describe('Detalle de un traslado', () => {
  it('un posible traslado se ve como Traslado con signo de su dirección y se puede marcar', async () => {
    detalle('e')
    expect(await screen.findByText('Posible traslado ↔ (sale)')).toBeInTheDocument()
    expect(screen.getByText(/^-/)).toBeInTheDocument()
    await userEvent.click(screen.getByText('Marcar como traslado entre mis cuentas'))
    await waitFor(() =>
      expect(api.editarMovimiento).toHaveBeenCalledWith('e', expect.objectContaining({ categoria: 'Transferencia' }))
    )
  })

  it('"Es un gasto real" deja la marca no_es_traslado', async () => {
    detalle('e')
    await userEvent.click(await screen.findByText('Es un gasto real'))
    await waitFor(() =>
      expect(api.editarMovimiento).toHaveBeenCalledWith('e', { notas: expect.stringContaining('no_es_traslado') })
    )
  })

  it('vincular con la contraparte marca las dos patas', async () => {
    detalle('e')
    await userEvent.click(await screen.findByText('Vincular con su contraparte'))
    await userEvent.click(await screen.findByText('Vincular'))
    await waitFor(() => expect(api.editarMovimiento).toHaveBeenCalledTimes(2))
    expect(api.editarMovimiento).toHaveBeenCalledWith('i', expect.objectContaining({ categoria: 'Transferencia' }))
  })

  it('una transferencia a un tercero sin pista se ve como Gasto', async () => {
    detalle('t')
    expect(await screen.findByText('Gasto')).toBeInTheDocument()
  })
})
