// Punto de partida dentro de «Traer movimientos»: aparece arriba la primera vez, se puede
// posponer, y avisa cuántos correos anteriores a la fecha de inicio no se muestran.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [{ id: 'c1', nombre: 'Bancolombia Ahorros', saldo: 100000, moneda: 'COP', tipo: 'ahorro', icono: 'B' }]

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  sincronizarCorreos: vi.fn(),
  puntoDePartida: vi.fn(),
  guardarPuntoDePartida: vi.fn(),
  coberturaPuntoDePartida: vi.fn(),
  conciliacionPuntoDePartida: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ nombres: ['Otros'], iconoDe: () => '' }) }))

import { DialogosProvider } from '../lib/DialogosContext'
import Sincronizacion from '../screens/Sincronizacion'

const estado = (pp) => ({ meses: [], cuentas: [], sin_cuenta: [], ultima_sync: null, tareas: [], punto_partida: pp })

function montar(ruta = '/sincronizacion') {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[ruta]}>
        <Routes>
          <Route path="/sincronizacion" element={<Sincronizacion />} />
          <Route path="/movimientos-correo" element={<Sincronizacion modo="correo" />} />
        </Routes>
      </MemoryRouter>
    </DialogosProvider>
  )
}

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
  Object.values(api).forEach((f) => f.mockReset())
  api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', etiqueta: 'gastos' })
  api.correosPendientes.mockResolvedValue([])
  api.extractosCorreo.mockResolvedValue([])
  api.clavePdfEstado.mockResolvedValue({})
  api.coberturaPuntoDePartida.mockResolvedValue({ meses: [], cuentas: [] })
  api.conciliacionPuntoDePartida.mockResolvedValue({ cuentas: [] })
})

describe('Traer movimientos y el punto de partida', () => {
  it('la primera vez es el primer paso del asistente: un botón que abre la elección', async () => {
    api.sincronizacionEstado.mockResolvedValue(estado({ definido: false, modo: null, fecha: null, saldos: {}, anteriores: { correos: 0, extractos: 0 } }))
    montar()
    expect(await screen.findByTestId('paso-titulo')).toHaveTextContent('¿Desde cuándo leo tu correo?')
    expect(screen.queryByTestId('punto-partida-elegir')).toBeNull() // la elección está detrás del botón, no suelta en la pantalla
    fireEvent.click(screen.getByTestId('tarea-punto_partida'))
    expect(await screen.findByTestId('punto-partida-elegir')).toBeTruthy()
  })

  it('«Decidir después» lo oculta y no vuelve a insistir pronto', async () => {
    api.sincronizacionEstado.mockResolvedValue(estado({ definido: false, modo: null, fecha: null, saldos: {}, anteriores: { correos: 0, extractos: 0 } }))
    const { unmount } = montar()
    fireEvent.click(await screen.findByTestId('tarea-punto_partida'))
    await screen.findByTestId('punto-partida-elegir')
    fireEvent.click(screen.getByRole('button', { name: 'Decidir después' }))
    await waitFor(() => expect(screen.queryByTestId('punto-partida-elegir')).toBeNull())
    unmount()
    montar()
    await screen.findByRole('heading', { name: 'Traer extractos' })
    expect(await screen.findByTestId('todo-al-dia')).toBeTruthy()
    expect(screen.queryByTestId('tarea-punto_partida')).toBeNull()
    expect(screen.queryByTestId('punto-partida-elegir')).toBeNull()
  })

  it('una vez elegido no estorba y avisa cuántos correos anteriores no se muestran', async () => {
    api.sincronizacionEstado.mockResolvedValue(estado({
      definido: true, modo: 'hoy', fecha: '2026-10-01', saldos: {}, anteriores: { correos: 4, extractos: 0 },
    }))
    montar('/movimientos-correo') // los correos anteriores a la fecha de inicio se avisan en «Movimientos del correo»
    await screen.findByRole('heading', { name: 'Movimientos del correo' })
    expect(screen.queryByTestId('punto-partida-elegir')).toBeNull()
    fireEvent.click(await screen.findByTestId('ver-todo'))
    fireEvent.click(await screen.findByTestId('tab-correos'))
    expect(await screen.findByTestId('correos-anteriores')).toHaveTextContent('4 correos anteriores a tu fecha de inicio no se muestran.')
  })
})
