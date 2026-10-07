import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const supa = vi.hoisted(() => ({
  getSession: vi.fn(),
  signOut: vi.fn(),
}))
vi.mock('../lib/supabase', () => ({ supabase: { auth: supa } }))

import { api, MSG_ERROR_SERVIDOR, MSG_SESION_VENCIDA, MSG_SIN_CONEXION } from '../lib/api'

function respuesta(status, cuerpo = {}) {
  return { ok: status >= 200 && status < 300, status, json: async () => cuerpo }
}

beforeEach(() => {
  supa.getSession.mockResolvedValue({ data: { session: { access_token: 'tok' } } })
  supa.signOut.mockResolvedValue({})
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('api.js: errores de red y de servidor', () => {
  it('un fetch fallido ("Failed to fetch") se traduce a un mensaje en español', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api.cuentas()).rejects.toThrow(MSG_SIN_CONEXION)
  })

  it('un 5xx muestra un mensaje amable y conserva el status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(503, { detail: 'upstream connect error' })))
    const err = await api.cuentas().catch((e) => e)
    expect(err.message).toBe(MSG_ERROR_SERVIDOR)
    expect(err.status).toBe(503)
  })

  it('un 401 con sesión cierra la sesión y avisa por evento', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(401, { detail: 'jwt expired' })))
    const aviso = vi.fn()
    window.addEventListener('cuadrame:sesion-vencida', aviso)
    await expect(api.cuentas()).rejects.toThrow(MSG_SESION_VENCIDA)
    window.removeEventListener('cuadrame:sesion-vencida', aviso)
    expect(supa.signOut).toHaveBeenCalledTimes(1)
    expect(aviso).toHaveBeenCalledTimes(1)
  })

  it('un 401 sin sesión (por ejemplo un login fallido) no cierra sesión ni cambia el mensaje', async () => {
    supa.getSession.mockResolvedValue({ data: { session: null } })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(401, { detail: 'Credenciales inválidas' })))
    await expect(api.cuentas()).rejects.toThrow('Credenciales inválidas')
    expect(supa.signOut).not.toHaveBeenCalled()
  })

  it('no rompe los mensajes de detalle (4xx) ni el consentimiento requerido', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(400, { detail: 'La cuenta ya existe' })))
    await expect(api.cuentas()).rejects.toThrow('La cuenta ya existe')

    const evento = vi.fn()
    window.addEventListener('cuadrame:consentimiento', evento)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respuesta(403, { detail: { codigo: 'consentimiento_requerido', finalidad: 'correos', mensaje: 'Falta autorización' } })
      )
    )
    const err = await api.cuentas().catch((e) => e)
    window.removeEventListener('cuadrame:consentimiento', evento)
    expect(err.message).toBe('Falta autorización')
    expect(err.codigo).toBe('consentimiento_requerido')
    expect(evento).toHaveBeenCalledTimes(1)
  })
})
