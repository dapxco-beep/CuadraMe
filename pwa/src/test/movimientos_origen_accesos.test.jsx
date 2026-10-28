// Movimientos: filtro «Origen» y accesos fijos «Correos por revisar (N)» / «Correos descartados (M)».
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => {
  const valor = { cuentas: [{ id: 'c1', nombre: 'Nu', saldo: 1, moneda: 'COP', tipo: 'ahorro' }], cargando: false, error: '', recargar: () => Promise.resolve() }
  return { useCuentas: () => valor }
})
vi.mock('../lib/CategoriasContext', () => {
  const valor = { categorias: [], activas: [], nombres: ['Otros'], cargando: false, recargar: () => Promise.resolve(), iconoDe: () => '💳', colorDe: () => null }
  return { useCategorias: () => valor }
})

import { DialogosProvider } from '../lib/DialogosContext'
import Movimientos from '../screens/Movimientos'
import { vaciarCachesListas } from '../lib/useEstadoLista'

const MOV = {
  id: 'm1', cuenta_id: 'c1', descripcion: 'Tienda', monto: 5000, tipo: 'expense', categoria: 'Otros',
  fecha: '2026-10-06T10:00:00', cat_confirmada: true, origen: 'manual', canales: ['manual'],
}

function Estado() {
  const l = useLocation()
  return <p data-testid="ruta">{l.pathname}{l.search}|{JSON.stringify(l.state)}</p>
}

const montar = () =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={['/movimientos']}>
        <Estado />
        <Routes>
          <Route path="/movimientos" element={<Movimientos />} />
          <Route path="/sincronizacion" element={<p>sinc</p>} />
        </Routes>
      </MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => {
  vi.clearAllMocks()
  vaciarCachesListas()
  window.localStorage.clear()
  window.sessionStorage.clear()
  Object.assign(api, {
    movimientos: vi.fn().mockResolvedValue([MOV]),
    conteoPorRevisar: vi.fn().mockResolvedValue({ auto: 0, otros: 0, total: 0 }),
    correosPendientes: vi.fn().mockResolvedValue([]),
    correosLista: vi.fn().mockResolvedValue([]),
    gmailEstado: vi.fn().mockResolvedValue({ conectado: false }),
  })
})

describe('Movimientos: origen y accesos al correo', () => {
  it('sin correos pendientes ni descartados no muestra los accesos', async () => {
    montar()
    await screen.findByText('Tienda')
    expect(screen.queryByTestId('accesos-correo')).not.toBeInTheDocument()
  })

  it('muestra «Correos descartados (M)» y lleva a Ver todo → Correos → Descartados', async () => {
    api.correosLista.mockResolvedValue([{ id: 'k1' }, { id: 'k2' }])
    montar()
    await userEvent.click(await screen.findByRole('button', { name: /^Correos descartados \(2\)/ }))
    expect(screen.getByTestId('ruta').textContent).toContain('/movimientos-correo')
    expect(screen.getByTestId('ruta').textContent).toContain('correos-descartados')
  })

  it('muestra «Correos por revisar (N)» cuando hay pendientes', async () => {
    api.correosPendientes.mockResolvedValue([{ id: 'p1', comercio: 'Cámara de Comercio', monto: 390500, estado: 'pendiente' }])
    montar()
    expect(await screen.findByRole('button', { name: /^Correos por revisar \(1\)/ })).toBeInTheDocument()
  })

  it('el filtro Origen pide al servidor solo esos movimientos', async () => {
    montar()
    await screen.findByText('Tienda')
    await userEvent.click(screen.getByRole('button', { name: /filtros/i }))
    await userEvent.selectOptions(screen.getByLabelText('Filtrar por origen'), 'correo')
    await waitFor(() =>
      expect(api.movimientos.mock.calls.some((c) => c[2]?.origen === 'correo')).toBe(true)
    )
  })
})
