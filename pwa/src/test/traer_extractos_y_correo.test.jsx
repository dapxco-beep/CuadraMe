import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  sincronizarCorreos: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({ useCuentas: () => ({ cuentas: [], cargando: false, error: '', recargar: vi.fn() }) }))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ nombres: [], iconoDe: () => '' }) }))

import { DialogosProvider } from '../lib/DialogosContext'
import Sincronizacion from '../screens/Sincronizacion'
import TarjetaMovimientosCorreo from '../components/TarjetaMovimientosCorreo'
import { GRUPOS, ITEMS_MAS, buscarDestinos } from '../lib/navegacion'

function Sonda() {
  return <p data-testid="ruta">{useLocation().pathname}</p>
}

const montarTarjeta = (props) =>
  render(<MemoryRouter><TarjetaMovimientosCorreo {...props} /></MemoryRouter>)

describe('tarjeta «Movimientos del correo» (en Movimientos)', () => {
  it('conectado: dice cuántos esperan, deja traerlos ya y lleva a la pantalla completa', () => {
    const onTraer = vi.fn()
    montarTarjeta({ conectado: true, porRevisar: 3, onTraer })
    expect(screen.getByText('3 avisos esperan tu revisión.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Traer del correo/ }))
    expect(onTraer).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('link', { name: 'Revisar (3)' })).toHaveAttribute('href', '/movimientos-correo')
  })

  it('un solo aviso usa el singular y sin pendientes ofrece «Ver todo»', () => {
    const { unmount } = montarTarjeta({ conectado: true, porRevisar: 1 })
    expect(screen.getByText('1 aviso espera tu revisión.')).toBeTruthy()
    unmount()
    montarTarjeta({ conectado: true, porRevisar: 0 })
    expect(screen.getByRole('link', { name: 'Ver todo' })).toBeTruthy()
  })

  it('sin correo conectado invita a conectarlo en vez de ofrecer traer', () => {
    montarTarjeta({ conectado: false })
    expect(screen.getByRole('link', { name: 'Conectar mi correo' })).toHaveAttribute('href', '/movimientos-correo')
    expect(screen.queryByRole('button', { name: /Traer del correo/ })).toBeNull()
  })

  it('mientras lee no deja pulsar de nuevo y muestra el avance; el aviso queda en la región de estado', () => {
    montarTarjeta({ conectado: true, leyendo: true, aviso: 'ignorado mientras lee' })
    expect(screen.getByRole('button', { name: /Leyendo/ })).toBeDisabled()
    expect(screen.getByTestId('estado-correo')).toHaveTextContent('Leyendo tu correo…')
  })

  it('mientras no se sabe si está conectado, el botón espera', () => {
    montarTarjeta({ conectado: null })
    expect(screen.getByRole('button', { name: /Traer del correo/ })).toBeDisabled()
  })
})

describe('el menú separa «Traer extractos» y «Movimientos del correo»', () => {
  it('los dos viven en «Anotar y traer»; «Traer movimientos» ya no existe', () => {
    const datos = GRUPOS.find((g) => g.id === 'datos').items.map((i) => i.label)
    expect(datos).toContain('Traer extractos')
    expect(datos).toContain('Movimientos del correo')
    expect(ITEMS_MAS.some((i) => i.label === 'Traer movimientos')).toBe(false)
    expect(ITEMS_MAS.find((i) => i.label === 'Movimientos del correo').to).toBe('/movimientos-correo')
    expect(ITEMS_MAS.find((i) => i.label === 'Traer extractos').to).toBe('/sincronizacion')
  })

  it('el buscador encuentra cada uno por sus palabras', () => {
    expect(buscarDestinos('avisos del banco')[0].to).toBe('/movimientos-correo')
    expect(buscarDestinos('extracto pdf')[0].to).toBe('/sincronizacion')
  })
})

describe('las dos caras de la pantalla', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
    Object.values(api).forEach((f) => f.mockReset())
    api.sincronizacionEstado.mockResolvedValue({ meses: [], cuentas: [], sin_cuenta: [], tareas: [], ultima_sync: null })
    api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
    api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com' })
    api.extractosCorreo.mockResolvedValue([])
    api.clavePdfEstado.mockResolvedValue({})
    api.correosPendientes.mockResolvedValue([])
  })

  const montar = (ruta, state) =>
    render(
      <DialogosProvider>
        <MemoryRouter initialEntries={[{ pathname: ruta, state }]}>
          <Routes>
            <Route path="/sincronizacion" element={<Sincronizacion />} />
            <Route path="/movimientos-correo" element={<Sincronizacion modo="correo" />} />
          </Routes>
          <Sonda />
        </MemoryRouter>
      </DialogosProvider>
    )

  it('/sincronizacion se llama «Traer extractos» y /movimientos-correo «Movimientos del correo»', async () => {
    const { unmount } = montar('/sincronizacion')
    expect(await screen.findByRole('heading', { name: 'Traer extractos' })).toBeTruthy()
    unmount()
    montar('/movimientos-correo')
    expect(await screen.findByRole('heading', { name: 'Movimientos del correo' })).toBeTruthy()
  })

  it('la línea de estado de «Movimientos del correo» habla solo de avisos, sin extractos', async () => {
    montar('/movimientos-correo')
    const linea = await screen.findByTestId('estado-gmail-linea')
    expect(linea).toHaveTextContent('Gmail conectado · leyendo los avisos de tu banco')
    expect(linea.textContent).not.toMatch(/extracto/i)
  })

  it('un enlace viejo que pide los correos en /sincronizacion se lleva a /movimientos-correo', async () => {
    montar('/sincronizacion', { abrir: 'correos-descartados' })
    expect(await screen.findByRole('heading', { name: 'Movimientos del correo' })).toBeTruthy()
    expect(screen.getByTestId('ruta').textContent).toBe('/movimientos-correo')
  })

  it('y al revés: pedir subir un archivo en /movimientos-correo se lleva a /sincronizacion', async () => {
    montar('/movimientos-correo', { abrir: 'subir' })
    expect(await screen.findByRole('heading', { name: 'Traer extractos' })).toBeTruthy()
    expect(screen.getByTestId('ruta').textContent).toBe('/sincronizacion')
  })
})
