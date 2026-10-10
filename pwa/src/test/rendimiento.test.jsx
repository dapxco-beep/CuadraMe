// Fluidez y mala señal: «último visto» (leer sin red), cola de movimientos sin conexión y
// arranque en paralelo desde index.html (window.__arranque).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const supa = vi.hoisted(() => ({
  getSession: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe() {} } } })),
}))
vi.mock('../lib/supabase', () => ({ supabase: { auth: supa } }))

import { api, configurarCache } from '../lib/api'
import { leerVisto, olvidarVistos, visto } from '../lib/ultimoVisto'
import { encolarMovimiento, enviarPendientes, pendientesDe, vaciarCola } from '../lib/colaOffline'

const CUENTAS = [{ id: 'c1', nombre: 'Nu', saldo: 1000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]

beforeEach(() => {
  supa.getSession.mockResolvedValue({ data: { session: { access_token: 'tok', user: { id: 'u1' } } } })
  window.localStorage.clear()
  configurarCache({ ttl: 0, vistos: true })
})
afterEach(() => {
  vi.unstubAllGlobals()
  olvidarVistos()
  configurarCache({ ttl: 0, vistos: false })
  delete window.__arranque
})

describe('último visto', () => {
  it('recuerda la última lectura y la entrega al instante a quien la pida', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => CUENTAS })))
    expect(visto.cuentas()).toBeUndefined()
    await api.cuentas()
    const v = visto.cuentas()
    expect(v).toEqual(CUENTAS)
    v[0].saldo = 5 // es una copia: no contamina lo guardado
    expect(visto.cuentas()[0].saldo).toBe(1000)
  })

  it('sin conexión devuelve lo último visto y avisa; con error de servidor sigue fallando', async () => {
    const f = vi.fn(async () => ({ ok: true, status: 200, json: async () => CUENTAS }))
    vi.stubGlobal('fetch', f)
    await api.cuentas()
    const avisos = []
    const oir = () => avisos.push('guardados')
    window.addEventListener('cuadrame:datos-guardados', oir)

    f.mockImplementation(async () => {
      throw new TypeError('Failed to fetch')
    })
    await expect(api.cuentas()).resolves.toEqual(CUENTAS)
    expect(avisos).toEqual(['guardados'])

    // una ruta que nunca se vio no tiene copia: el error de conexión sigue siendo un error
    await expect(api.metas()).rejects.toThrow()

    f.mockImplementation(async () => ({ ok: false, status: 500, json: async () => ({}) }))
    await expect(api.cuentas()).rejects.toThrow()
    window.removeEventListener('cuadrame:datos-guardados', oir)
  })

  it('al cerrar sesión se borra de memoria y del celular', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => CUENTAS })))
    await api.cuentas()
    window.localStorage.setItem('cuadrame:visto:u1', '{}')
    expect(leerVisto('/cuentas')).toEqual(CUENTAS)
    olvidarVistos()
    expect(leerVisto('/cuentas')).toBeUndefined()
    expect(window.localStorage.getItem('cuadrame:visto:u1')).toBeNull()
    expect(window.localStorage.getItem('cuadrame:visto-uid')).toBeNull()
  })

  it('en el celular solo se guardan lecturas permitidas (no claves ni correos)', async () => {
    vi.useFakeTimers()
    try {
      vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ api_key: 'secreta' }) })))
      await api.cuentas()
      await api.gmailEstado()
      await vi.advanceTimersByTimeAsync(2500)
      const guardado = window.localStorage.getItem('cuadrame:visto:u1') || ''
      expect(guardado).toContain('/cuentas')
      expect(guardado).not.toContain('correos')
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('arranque en paralelo (index.html)', () => {
  it('recoge una sola vez la lectura ya lanzada si es de la misma sesión', async () => {
    const f = vi.fn(async () => ({ ok: true, status: 200, json: async () => [{ id: 'red' }] }))
    vi.stubGlobal('fetch', f)
    window.__arranque = { t: 'tok', en: Date.now(), p: { '/cuentas': Promise.resolve([{ id: 'temprana' }]) } }
    expect(await api.cuentas()).toEqual([{ id: 'temprana' }])
    expect(f).not.toHaveBeenCalled()
    expect((await api.cuentas())[0].id).toBe('red') // ya no queda: la segunda va a la red
  })

  it('ignora la lectura temprana si falló o es de otra sesión', async () => {
    const f = vi.fn(async () => ({ ok: true, status: 200, json: async () => [{ id: 'red' }] }))
    vi.stubGlobal('fetch', f)
    window.__arranque = { t: 'tok', en: Date.now(), p: { '/cuentas': Promise.resolve(undefined) } }
    expect((await api.cuentas())[0].id).toBe('red')
    window.__arranque = { t: 'otro-token', en: Date.now(), p: { '/metas': Promise.resolve([{ id: 'x' }]) } }
    expect(await api.metas()).toEqual([{ id: 'red' }])
  })
})

describe('cola de movimientos sin conexión', () => {
  const dato = { cuenta_id: 'c1', descripcion: 'Tinto', monto: 3000, tipo: 'expense' }

  it('se guarda por usuario con la hora real del gasto y se envía en orden', async () => {
    expect(encolarMovimiento('u1', dato)).toBe(true)
    expect(encolarMovimiento('u1', { ...dato, descripcion: 'Pan' })).toBe(true)
    expect(encolarMovimiento('u2', dato)).toBe(true)
    expect(pendientesDe('u1')).toHaveLength(2)
    expect(pendientesDe('u1')[0].datos.fecha).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/)

    const enviados = []
    const r = await enviarPendientes('u1', async (d) => enviados.push(d.descripcion))
    expect(enviados).toEqual(['Tinto', 'Pan'])
    expect(r).toMatchObject({ enviados: 2, descartados: 0, quedan: 0 })
    expect(pendientesDe('u2')).toHaveLength(1) // lo de otro usuario no se toca
    vaciarCola()
  })

  it('si sigue sin red se detiene y conserva lo pendiente', async () => {
    encolarMovimiento('u1', dato)
    encolarMovimiento('u1', { ...dato, descripcion: 'Pan' })
    const err = Object.assign(new Error('sin red'), { sinConexion: true })
    const r = await enviarPendientes('u1', async () => {
      throw err
    })
    expect(r).toMatchObject({ enviados: 0, quedan: 2 })
    vaciarCola()
  })

  it('un duplicado (409) se descarta sin repetirlo', async () => {
    encolarMovimiento('u1', dato)
    const r = await enviarPendientes('u1', async () => {
      throw Object.assign(new Error('ya está'), { status: 409 })
    })
    expect(r).toMatchObject({ enviados: 0, descartados: 1, quedan: 0 })
  })
})
