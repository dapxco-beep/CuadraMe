// Sincronización: subir extracto del mes, nombres homónimos y ventana de meses desplazable.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const CUENTAS = [
  { id: 'n1', nombre: 'Nu Colombia', tipo: 'ahorro', saldo: 0, moneda: 'COP' },
  { id: 'n2', nombre: 'Nu Colombia', tipo: 'credito', alias_tarjeta: '4821', saldo: 0, moneda: 'COP' },
]
const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  correosPendientes: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ nombres: ['Otros'], iconoDe: () => '🏷️' }) }))

import { DialogosProvider } from '../lib/DialogosContext'
import Sincronizacion from '../screens/Sincronizacion'
import { moverMes, nombresDesambiguados } from '../lib/sincronizacion'

const MESES = ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10']
const celda = (mes, estado, extra = {}) => ({ mes, estado, movimientos: 0, conciliados: 0, por_confirmar: 0, extractos: 0, ...extra })
const estadoCon = (meses) => ({
  meses: meses.map((clave) => ({ clave, etiqueta: clave })),
  cuentas: [
    { id: 'n1', nombre: 'Nu Colombia', meses: meses.map((m) => celda(m, 'sin_extracto', { movimientos: 62, por_confirmar: 55 })) },
    { id: 'n2', nombre: 'Nu Colombia', meses: meses.map((m) => celda(m, 'vacio')) },
  ],
  sin_cuenta: [],
  tareas: [],
  ultima_sync: null,
})

function Destino() {
  const l = useLocation()
  return <p data-testid="destino">{JSON.stringify(l.state)}</p>
}
const montar = () =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={['/sincronizacion']}>
        <Routes>
          <Route path="/sincronizacion" element={<Sincronizacion />} />
          <Route path="/conciliacion" element={<Destino />} />
        </Routes>
      </MemoryRouter>
    </DialogosProvider>
  )

// La cobertura por mes vive en «Ver todo» → «Por mes».
const abrirExtractos = async () => {
  fireEvent.click(await screen.findByTestId('ver-todo'))
  fireEvent.click(await screen.findByTestId('tab-meses'))
}

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  api.sincronizacionEstado.mockResolvedValue(estadoCon(MESES))
  api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
  api.gmailEstado.mockResolvedValue({ conectado: false })
  api.extractosCorreo.mockResolvedValue([])
  api.clavePdfEstado.mockResolvedValue({})
  api.correosPendientes.mockResolvedValue([])
})

describe('helpers', () => {
  it('desambigua cuentas homónimas con tipo y últimos dígitos', () => {
    const n = nombresDesambiguados(estadoCon(MESES).cuentas, CUENTAS)
    expect(n.n1).toBe('Nu Colombia (Ahorros)')
    expect(n.n2).toBe('Nu Colombia (Crédito ••4821)')
    expect(nombresDesambiguados([{ id: 'x', nombre: 'Nequi' }], [])).toEqual({ x: 'Nequi' })
  })
  it('mueve meses cruzando años', () => {
    expect(moverMes('2026-02', -6)).toBe('2025-08')
    expect(moverMes('2025-11', 3)).toBe('2026-02')
  })
})

describe('Sincronización: cuadrícula', () => {
  it('nombres homónimos distinguibles en la cuadrícula', async () => {
    montar()
    await abrirExtractos()
    expect(await screen.findByRole('button', { name: /Nu Colombia \(Ahorros\), mayo 2026/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Nu Colombia \(Crédito ••4821\), mayo 2026/ })).toBeTruthy()
  })

  it('"Subir el extracto de este mes" abre la hoja de subir archivo con cuenta y mes, sin salir del centro', async () => {
    montar()
    await abrirExtractos()
    fireEvent.click(await screen.findByRole('button', { name: /Nu Colombia \(Ahorros\), mayo 2026/ }))
    const det = screen.getByRole('region', { name: 'Detalle del mes' })
    fireEvent.click(within(det).getByRole('button', { name: 'Subir el extracto de este mes' }))
    expect(await screen.findByText(/Sube el extracto de/)).toHaveTextContent('mayo 2026 de Nu Colombia')
    expect(screen.getByLabelText('Archivos a subir')).toBeTruthy()
    expect(screen.queryByTestId('destino')).toBeNull()
  })

  it('"Meses anteriores" pide la ventana anterior al servidor', async () => {
    montar()
    await abrirExtractos()
    await screen.findByRole('button', { name: /Nu Colombia \(Ahorros\), mayo 2026/ })
    api.sincronizacionEstado.mockResolvedValue(estadoCon(['2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04']))
    const hoy = new Date()
    const esperado = moverMes(`${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`, -6)
    fireEvent.click(screen.getByRole('button', { name: /Meses anteriores/ }))
    await waitFor(() => expect(api.sincronizacionEstado).toHaveBeenLastCalledWith(esperado))
  })

  it('si el servidor ignora la ventana, se esconden los botones de desplazar', async () => {
    montar()
    await abrirExtractos()
    await screen.findByRole('button', { name: /Nu Colombia \(Ahorros\), mayo 2026/ })
    fireEvent.click(screen.getByRole('button', { name: /Meses anteriores/ })) // responde la misma ventana
    await waitFor(() => expect(screen.queryByRole('button', { name: /Meses anteriores/ })).toBeNull())
  })
})
