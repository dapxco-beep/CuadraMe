// Caché y deduplicación de lecturas en api.js + medición de peticiones por pantalla
// (fetch simulado: se cuenta cuántas peticiones HTTP salen realmente).
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const supa = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn(), onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe() {} } } })) }))
vi.mock('../lib/supabase', () => ({ supabase: { auth: supa } }))
vi.mock('../lib/AuthContext', () => {
  const valor = { usuario: { id: 'u1', nombre: 'Dani Prueba', email: 'd@x.co' }, cargando: false, logout: () => {} } // estable entre renders
  return { useAuth: () => valor }
})

import { api, configurarCache, estadisticasPeticiones, invalidarCache } from '../lib/api'
import { ThemeProvider } from '../lib/ThemeContext'
import { BloqueoProvider } from '../lib/BloqueoContext'
import { CategoriasProvider } from '../lib/CategoriasContext'
import { CuentasProvider } from '../lib/CuentasContext'
import { DialogosProvider } from '../lib/DialogosContext'
import Inicio from '../screens/Inicio'
import Perfil from '../screens/Perfil'

let llamadas = []
let respuestas = {}
function instalarFetch() {
  llamadas = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, op = {}) => {
      const ruta = String(url).replace(/^https?:\/\/[^/]+/, '')
      llamadas.push(`${op.method || 'GET'} ${ruta}`)
      await new Promise((r) => setTimeout(r, 5)) // un poco de latencia para que se solapen
      const base = ruta.split('?')[0]
      const cuerpo = respuestas[ruta] ?? respuestas[base] ?? (/\/(cuentas|movimientos|categorias|reglas|deudas|metas)/.test(base) ? [] : {})
      return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(cuerpo)) }
    })
  )
}

beforeEach(() => {
  supa.getSession.mockResolvedValue({ data: { session: { access_token: 'tok', user: { id: 'u1' } } } })
  respuestas = {
    '/cuentas': [{ id: 'c1', nombre: 'Nu', saldo: 1000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }],
    '/correos/gmail/estado': { conectado: true },
    '/sincronizacion/estado': { tareas: [] },
    '/reportes/mensual': { salud: { score: 60, tips: ['ok'] }, top_categorias: [], total_gastos: 0, total_ingresos: 0 },
    '/presupuestos/en-mi-bolsillo': { saldo_total: 1000, disponible_real: 500, disponible_real_por_dia: 10, recurrentes_pendientes_mes: 0, aportes_comprometidos_mes: 0 },
  }
  instalarFetch()
})
afterEach(() => {
  vi.unstubAllGlobals()
  configurarCache({ ttl: 0 })
})

describe('api.js: lecturas', () => {
  it('GET idénticos simultáneos comparten una sola petición', async () => {
    configurarCache({ ttl: 0 })
    const [a, b, c] = await Promise.all([api.cuentas(), api.cuentas(), api.cuentas()])
    expect(llamadas).toEqual(['GET /cuentas'])
    expect(a).toEqual(b)
    a[0].nombre = 'MODIFICADO'
    expect(c[0].nombre).toBe('Nu') // cada quien recibe su copia
  })

  it('con TTL la respuesta se reutiliza, y una escritura la invalida', async () => {
    configurarCache({ ttl: 5000 })
    await api.cuentas()
    await api.cuentas()
    expect(llamadas).toEqual(['GET /cuentas'])
    await api.crearCuenta({ nombre: 'X' })
    await api.cuentas()
    expect(llamadas).toEqual(['GET /cuentas', 'POST /cuentas', 'GET /cuentas'])
  })

  it('una lectura que arrancó antes de una escritura no deja datos viejos en caché', async () => {
    configurarCache({ ttl: 5000 })
    const lectura = api.cuentas()
    await api.crearCuenta({ nombre: 'X' }) // invalida mientras la lectura está en vuelo
    await lectura
    await api.cuentas()
    expect(llamadas.filter((l) => l === 'GET /cuentas')).toHaveLength(2)
  })

  it('no mezcla datos entre usuarios', async () => {
    configurarCache({ ttl: 5000 })
    await api.cuentas()
    supa.getSession.mockResolvedValue({ data: { session: { access_token: 't2', user: { id: 'u2' } } } })
    await api.cuentas()
    expect(llamadas).toEqual(['GET /cuentas', 'GET /cuentas'])
  })

  it('un error no se guarda en caché', async () => {
    configurarCache({ ttl: 5000 })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({}) }).mockResolvedValue({ ok: true, status: 200, json: async () => [] }))
    await expect(api.cuentas()).rejects.toThrow()
    await expect(api.cuentas()).resolves.toEqual([])
  })
})

function Envuelta({ children }) {
  return (
    <ThemeProvider>
      <BloqueoProvider>
        <DialogosProvider>
          <CategoriasProvider>
            <CuentasProvider>
              <MemoryRouter>
                {children}
              </MemoryRouter>
            </CuentasProvider>
          </CategoriasProvider>
        </DialogosProvider>
      </BloqueoProvider>
    </ThemeProvider>
  )
}

async function medir(Pantalla, espera, opciones) {
  configurarCache(opciones)
  instalarFetch()
  estadisticasPeticiones(true)
  // StrictMode como en `vite dev` (donde se hizo la prueba E2E): monta cada efecto dos veces
  const { unmount } = render(
    <StrictMode>
      <Envuelta>
        <Pantalla />
      </Envuelta>
    </StrictMode>
  )
  await espera()
  await new Promise((r) => setTimeout(r, 150)) // deja terminar lo que se pide después
  unmount()
  return [...llamadas]
}

describe('Medición: peticiones al abrir Inicio', () => {
  it('antes (sin caché) vs después (dedupe + caché)', async () => {
    const espera = () => screen.findByText(/Hola, Dani/)
    const antes = await medir(Inicio, espera, { desactivar: true })
    const despues = await medir(Inicio, espera, { ttl: 5000 })
    const contar = (l) => l.reduce((m, x) => ({ ...m, [x]: (m[x] || 0) + 1 }), {})
    console.log('INICIO antes:', antes.length, JSON.stringify(contar(antes)))
    console.log('INICIO después:', despues.length, JSON.stringify(contar(despues)))
    expect(despues.length).toBeLessThan(antes.length)
    // ninguna ruta se pide más de una vez
    expect(Math.max(...Object.values(contar(despues)))).toBe(1)
  })
})

describe('Medición: peticiones al abrir Perfil', () => {
  it('antes vs después', async () => {
    const espera = () => screen.findAllByText(/Privacidad/)
    const antes = await medir(Perfil, espera, { desactivar: true })
    const despues = await medir(Perfil, espera, { ttl: 5000 })
    const contar = (l) => l.reduce((m, x) => ({ ...m, [x]: (m[x] || 0) + 1 }), {})
    console.log('PERFIL antes:', antes.length, JSON.stringify(contar(antes)))
    console.log('PERFIL después:', despues.length, JSON.stringify(contar(despues)))
    expect(despues.length).toBeLessThanOrEqual(antes.length)
    expect(Math.max(...Object.values(contar(despues)))).toBe(1)
  })
})
