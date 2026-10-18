import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

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
import { CLAVE_SYNC, actualizarDesdeCorreo, resumenActualizacion } from '../lib/sincronizarGmail'

const montar = () =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={['/movimientos']}>
        <Routes>
          <Route path="/movimientos" element={<Movimientos />} />
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
    movimientos: vi.fn().mockResolvedValue([]),
    conteoPorRevisar: vi.fn().mockResolvedValue({ auto: 0, otros: 0, total: 0 }),
    correosPendientes: vi.fn().mockResolvedValue([]),
    gmailEstado: vi.fn().mockResolvedValue({ conectado: true }),
    sincronizarCorreos: vi.fn().mockResolvedValue({ ok: true, completado: true, nuevos: 2 }),
  })
})

describe('actualizarDesdeCorreo', () => {
  it('lee solo el carril de movimientos y respeta los 5 minutos salvo gesto manual', async () => {
    expect(await actualizarDesdeCorreo()).toEqual({ nuevos: 2 })
    expect(api.sincronizarCorreos).toHaveBeenCalledWith({ tipo: 'movimientos' })
    expect((await actualizarDesdeCorreo()).omitido).toBe(true)
    expect(api.sincronizarCorreos).toHaveBeenCalledTimes(1)
    expect(await actualizarDesdeCorreo({ manual: true })).toEqual({ nuevos: 2 })
    expect(api.sincronizarCorreos).toHaveBeenCalledTimes(2)
  })
  it('sin Gmail conectado no llama; un error no lanza y no marca la hora', async () => {
    expect((await actualizarDesdeCorreo({ conectado: false })).omitido).toBe(true)
    api.sincronizarCorreos.mockResolvedValue({ ok: false, error: 'Se perdió el acceso a Gmail.' })
    const r = await actualizarDesdeCorreo()
    expect(r.error).toMatch(/Gmail/)
    expect(window.localStorage.getItem(CLAVE_SYNC)).toBeNull()
  })
  it('frases del aviso', () => {
    expect(resumenActualizacion({ nuevos: 2 })).toBe('Traje 2 movimientos nuevos')
    expect(resumenActualizacion({ nuevos: 1 })).toBe('Traje 1 movimiento nuevo')
    expect(resumenActualizacion({ nuevos: 0 })).toMatch(/nada nuevo en tu correo/)
  })
})

describe('Movimientos lee el correo al abrir', () => {
  it('muestra «Traje 2 movimientos nuevos», recarga «Por revisar» y el botón fuerza otra lectura', async () => {
    montar()
    expect(await screen.findByText('Traje 2 movimientos nuevos')).toBeInTheDocument()
    await waitFor(() => expect(api.correosPendientes.mock.calls.length).toBeGreaterThanOrEqual(2))
    expect(api.sincronizarCorreos).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Actualizar desde el correo' }))
    await waitFor(() => expect(api.sincronizarCorreos).toHaveBeenCalledTimes(2))
  })
})
