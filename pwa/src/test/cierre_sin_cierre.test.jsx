// Cierre de mes: "aún no hay cierre" es un estado normal (404 o null), sin petición ni error.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const supa = vi.hoisted(() => ({ getSession: vi.fn(async () => ({ data: { session: null } })), signOut: vi.fn() }))
vi.mock('../lib/supabase', () => ({ supabase: { auth: supa } }))

import { api, configurarCache } from '../lib/api'
import CierreMes from '../screens/CierreMes'
import { DialogosProvider } from '../lib/DialogosContext'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  configurarCache({ ttl: 0 })
})

const montar = () =>
  render(
    <DialogosProvider>
      <MemoryRouter>
        <CierreMes />
      </MemoryRouter>
    </DialogosProvider>
  )

describe('api.cierreMes', () => {
  it('un 404 se devuelve como null en vez de lanzar', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({ detail: 'No hay cierre' }) }))
    await expect(api.cierreMes('2026-09')).resolves.toBeNull()
  })
  it('otros errores siguen lanzando', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }))
    await expect(api.cierreMes('2026-09')).rejects.toThrow()
  })
})

describe('pantalla Cierre de mes', () => {
  it('si el mes no está en la lista no pide el cierre (cero 404 en consola)', async () => {
    const fetchMock = vi.fn(async (url) => {
      const ruta = String(url).replace(/^https?:\/\/[^/]+/, '')
      const cuerpo = ruta === '/cierre-mes' ? [] : ruta === '/cierre-mes/preferencias' ? { correo: false } : {}
      return { ok: true, status: 200, json: async () => cuerpo }
    })
    vi.stubGlobal('fetch', fetchMock)
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    montar()
    expect(await screen.findByText(/Aún no hay cierre de/)).toBeInTheDocument()
    const rutas = fetchMock.mock.calls.map(([u]) => String(u).replace(/^https?:\/\/[^/]+/, ''))
    expect(rutas.filter((r) => /^\/cierre-mes\/\d{4}-\d{2}$/.test(r))).toEqual([])
    expect(err).not.toHaveBeenCalled()
  })
})
