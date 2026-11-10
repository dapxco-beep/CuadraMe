import { describe, it, expect } from 'vitest'
import '../../public/compartido-logica.js'
import { tomarCompartidos } from '../lib/compartirArchivo'

const L = globalThis.CompartidoLogica
const f = (name, size) => ({ name, size })

describe('reglas del servicio (service worker)', () => {
  it('acepta pdf, csv y excel; rechaza el resto', () => {
    const { aceptados, rechazados } = L.filtrar([f('a.pdf', 10), f('b.CSV', 10), f('c.xlsx', 10), f('d.exe', 10), f('e.png', 10), f('vacio.pdf', 0)])
    expect(aceptados.map((x) => x.name)).toEqual(['a.pdf', 'b.CSV', 'c.xlsx'])
    expect(rechazados).toBe(3)
  })
  it('respeta los topes de tamaño y de cantidad', () => {
    expect(L.filtrar([f('g.pdf', 16 * 1024 * 1024)]).aceptados).toHaveLength(0)
    expect(L.filtrar([f('g.csv', 6 * 1024 * 1024)]).aceptados).toHaveLength(0)
    const muchos = Array.from({ length: 15 }, (_, i) => f(`x${i}.pdf`, 5))
    expect(L.filtrar(muchos).aceptados).toHaveLength(L.MAX_ARCHIVOS)
  })
  it('solo mismo origen (o sin origen) y vigencia de una hora', () => {
    expect(L.origenPermitido('https://malo.com', 'https://cuadrame.dapx.shop')).toBe(false)
    expect(L.origenPermitido('https://cuadrame.dapx.shop', 'https://cuadrame.dapx.shop')).toBe(true)
    expect(L.origenPermitido(null, 'https://cuadrame.dapx.shop')).toBe(true)
    expect(L.vigente(1000, 1000 + 59 * 60 * 1000)).toBe(true)
    expect(L.vigente(1000, 1000 + 61 * 60 * 1000)).toBe(false)
    expect(L.vigente(NaN, 5)).toBe(false)
  })
})

// Caché falso en memoria.
function cacheFalso(entradas) {
  const mapa = new Map(entradas)
  const cache = {
    keys: async () => [...mapa.keys()],
    match: async (k) => mapa.get(k),
    delete: async (k) => mapa.delete(k),
  }
  return { mapa, storage: { open: async () => cache } }
}
const resp = (cuerpo, nombre, guardado) =>
  new Response(cuerpo, { headers: { 'x-nombre': encodeURIComponent(nombre), 'x-guardado': String(guardado), 'content-type': 'application/pdf' } })

describe('tomarCompartidos (lado app)', () => {
  it('devuelve los archivos vigentes y vacía el caché', async () => {
    const ahora = 1_000_000
    const { mapa, storage } = cacheFalso([['/a', resp('hola', 'Extracto sep.pdf', ahora - 1000)]])
    const { archivos } = await tomarCompartidos({ cacheStorage: storage, ahora })
    expect(archivos).toHaveLength(1)
    expect(archivos[0].name).toBe('Extracto sep.pdf')
    expect(mapa.size).toBe(0)
  })
  it('descarta lo vencido o de tipo no permitido, pero igual limpia', async () => {
    const ahora = 10_000_000
    const { mapa, storage } = cacheFalso([
      ['/viejo', resp('x', 'viejo.pdf', ahora - 2 * 60 * 60 * 1000)],
      ['/malo', resp('x', 'virus.exe', ahora)],
    ])
    const r = await tomarCompartidos({ cacheStorage: storage, ahora })
    expect(r.archivos).toHaveLength(0)
    expect(r.rechazados).toHaveLength(1)
    expect(mapa.size).toBe(0)
  })
  it('sin caché disponible no falla', async () => {
    expect(await tomarCompartidos({ cacheStorage: null })).toEqual({ archivos: [], rechazados: [] })
  })
})
