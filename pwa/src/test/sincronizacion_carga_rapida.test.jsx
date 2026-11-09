// Carga rápida de «Traer movimientos»: se cuenta CUÁNDO sale cada llamada a la API.
// Antes del primer pintado solo van las 4 que deciden qué se ve; lo accesorio y los arreglos automáticos esperan.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(), sincronizacionPorCategorizar: vi.fn(), gmailEstado: vi.fn(), extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(), tarjetasVista: vi.fn(), cuadreSaldoInicialAuto: vi.fn(), reintentarErroresExtractos: vi.fn(),
  releerPendientes: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [], cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Otros'], iconoDe: () => '🏷️' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import Sincronizacion from '../screens/Sincronizacion'

const ESTADO = {
  meses: [{ clave: '2026-10', etiqueta: 'oct 26' }], cuentas: [], sin_cuenta: [], ultima_sync: null,
  tareas: [{ id: 'movimientos_por_categorizar', titulo: 'Movimientos por categorizar', detalle: 'x', cantidad: 1, ruta: '/sincronizacion#categorizar', opcional: true }],
  todos_extractos: { items: [], contadores: {}, resumen: '', sin_adjunto: [] },
}

function montar() {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={['/sincronizacion']}>
        <Routes><Route path="/sincronizacion" element={<Sincronizacion />} /></Routes>
      </MemoryRouter>
    </DialogosProvider>,
  )
}

let soltarEstado
beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
  Object.values(api).forEach((f) => f.mockReset())
  api.sincronizacionEstado.mockImplementation(() => new Promise((res) => { soltarEstado = () => res(ESTADO) }))
  api.gmailEstado.mockResolvedValue({ conectado: true })
  api.extractosCorreo.mockResolvedValue([])
  api.clavePdfEstado.mockResolvedValue({ configurada: false })
  api.tarjetasVista.mockResolvedValue({})
  api.sincronizacionPorCategorizar.mockResolvedValue({ items: [{ id: 'm1', descripcion: 'TIENDA', categoria: 'Otros', monto: 1, patron: 'T', cat_confirmada: false }], total: 1 })
  api.cuadreSaldoInicialAuto.mockResolvedValue({ registrados: [] })
  api.reintentarErroresExtractos.mockResolvedValue({})
  api.releerPendientes.mockResolvedValue({})
})

describe('Traer movimientos: orden de las llamadas', () => {
  it('mientras el estado no llega solo salen las 4 lecturas principales, en paralelo', async () => {
    montar()
    await waitFor(() => expect(api.sincronizacionEstado).toHaveBeenCalledTimes(1))
    expect(api.gmailEstado).toHaveBeenCalledTimes(1)
    expect(api.extractosCorreo).toHaveBeenCalledTimes(1)
    expect(api.clavePdfEstado).toHaveBeenCalledTimes(1)
    for (const f of [api.sincronizacionPorCategorizar, api.tarjetasVista, api.cuadreSaldoInicialAuto, api.reintentarErroresExtractos, api.releerPendientes]) {
      expect(f).not.toHaveBeenCalled()
    }
  })

  it('tras pintar salen los arreglos automáticos y las deudas; la cola solo al abrir «Poner categorías»', async () => {
    montar()
    await waitFor(() => expect(soltarEstado).toBeTypeOf('function'))
    soltarEstado()
    await waitFor(() => expect(api.cuadreSaldoInicialAuto).toHaveBeenCalledTimes(1))
    expect(api.reintentarErroresExtractos).toHaveBeenCalledTimes(1)
    expect(api.releerPendientes).toHaveBeenCalledTimes(1)
    expect(api.tarjetasVista).toHaveBeenCalledTimes(1)
    expect(api.sincronizacionPorCategorizar).not.toHaveBeenCalled()
    fireEvent.click(await screen.findByText('Movimientos por categorizar'))
    expect(await screen.findByTestId('cat-m1')).toBeInTheDocument()
    expect(api.sincronizacionPorCategorizar).toHaveBeenCalledTimes(1)
  })
})
