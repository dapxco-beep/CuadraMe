import { describe, it, expect, vi, afterEach } from 'vitest'
import { hoyISO, aFecha, msFecha } from '../lib/fechaLocal'
import { candidatosContraparte } from '../lib/traslados'
import { valorCDT } from '../lib/patrimonio'

afterEach(() => vi.useRealTimers())

describe('fechas locales (Colombia, UTC-5)', () => {
  it('a las 9 p. m. de Bogotá (02:00 UTC del día siguiente) «hoy» sigue siendo el día de Bogotá', () => {
    // El setup de pruebas fija TZ en Bogotá si no; aquí se construye la hora con el desfase local.
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-28T02:00:00Z'))
    const esperado = new Date().getTimezoneOffset() === 300 ? '2026-10-27' : null
    if (esperado) expect(hoyISO()).toBe(esperado)
    // Con cualquier zona: coincide con el calendario local, nunca con el UTC
    const d = new Date()
    expect(hoyISO()).toBe(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
  })

  it('«solo fecha» se lee como medianoche local, no UTC', () => {
    const d = aFecha('2026-10-08')
    expect([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours()]).toEqual([2026, 9, 8, 0])
    expect(aFecha('')).toBeNull()
    expect(aFecha('basura')).toBeNull()
    expect(Number.isNaN(msFecha(null))).toBe(true)
  })

  it('traslados: dos movimientos del mismo día (solo fecha) siguen siendo pareja', () => {
    const m = { id: 1, cuenta_id: 1, monto: 100, tipo: 'expense', fecha: '2026-10-08' }
    const o = { id: 2, cuenta_id: 2, monto: 100, tipo: 'income', fecha: '2026-10-09' }
    expect(candidatosContraparte(m, [o]).map((x) => x.id)).toEqual([2])
  })

  it('valorCDT con fechas de solo día cuenta días exactos', () => {
    const v = valorCDT(1000, 10, '2026-01-01', '2027-01-01')
    expect(v).toBeCloseTo(1000 * 1.1, 5)
  })
})
