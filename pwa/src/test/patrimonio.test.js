import { describe, expect, it } from 'vitest'
import {
  arcosDona, etiquetaMes, formatPct, puntosSerie, trazoArea, trazoLinea, valorCDT, variacion,
} from '../lib/patrimonio'

describe('valorCDT', () => {
  it('un año al 12 % E.A. multiplica por 1,12', () => {
    expect(valorCDT(10_000_000, 12, '2025-01-01', '2026-01-01')).toBeCloseTo(11_200_000, 2)
  })
  it('dos años compone: 1,12^2 = 1,2544', () => {
    expect(valorCDT(10_000_000, 12, '2025-01-01', '2027-01-01')).toBeCloseTo(12_544_000, 2)
  })
  it('antes del inicio vale el capital y después del vencimiento se congela', () => {
    expect(valorCDT(1000, 10, '2025-06-01', '2025-01-01')).toBe(1000)
    const venc = '2026-01-01'
    expect(valorCDT(1_000_000, 12, '2025-01-01', '2030-01-01', venc)).toBeCloseTo(1_120_000, 2)
  })
  it('datos incompletos dan 0 en vez de NaN', () => {
    expect(valorCDT(0, 12, '2025-01-01', '2026-01-01')).toBe(0)
    expect(valorCDT(1000, undefined, '2025-01-01', '2026-01-01')).toBe(0)
  })
})

describe('formatPct', () => {
  it('signo, coma decimal y guion si no hay dato', () => {
    expect(formatPct(12.345)).toBe('+12,3 %')
    expect(formatPct(-5)).toBe('-5,0 %')
    expect(formatPct(0)).toBe('0,0 %')
    expect(formatPct(null)).toBe('—')
    expect(formatPct(NaN)).toBe('—')
  })
})

describe('etiquetaMes', () => {
  it('convierte YYYY-MM en mes corto', () => {
    expect(etiquetaMes('2026-10')).toBe('Oct')
    expect(etiquetaMes('2026-01')).toBe('Ene')
  })
})

describe('arcosDona', () => {
  it('60/30/10 reparte la circunferencia en esas proporciones', () => {
    const r = 10
    const circ = 2 * Math.PI * r
    const arcos = arcosDona(
      [{ clase: 'a', pct: 60 }, { clase: 'b', pct: 30 }, { clase: 'c', pct: 10 }],
      r,
      0
    )
    expect(arcos.map((a) => a.largo / circ)).toEqual([
      expect.closeTo(0.6, 9), expect.closeTo(0.3, 9), expect.closeTo(0.1, 9),
    ])
    // cada arco empieza donde termina el anterior
    expect(arcos[0].desplazamiento).toBeCloseTo(0)
    expect(arcos[1].desplazamiento).toBeCloseTo(-0.6 * circ, 6)
    expect(arcos[2].desplazamiento).toBeCloseTo(-0.9 * circ, 6)
  })
  it('un solo activo ocupa el círculo completo sin hueco', () => {
    const [a] = arcosDona([{ clase: 'a', pct: 100 }], 10)
    expect(a.largo).toBeCloseTo(2 * Math.PI * 10)
  })
  it('vacío o en cero no dibuja nada', () => {
    expect(arcosDona([])).toEqual([])
    expect(arcosDona([{ clase: 'a', pct: 0 }])).toEqual([])
  })
})

describe('puntosSerie', () => {
  it('escala la serie [0, 10] al viewBox 100x60 con margen 4 y 8 % de aire', () => {
    // lo = -0.8, hi = 10.8 (rango 11,6). x: 4 y 96. y(0) = 4 + 52*(10,8... ver cálculo)
    const [p0, p1] = puntosSerie([0, 10], 100, 60, 4)
    expect(p0.x).toBe(4)
    expect(p1.x).toBe(96)
    expect(p0.y).toBeCloseTo(4 + (1 - 0.8 / 11.6) * 52, 6) // 52,41
    expect(p1.y).toBeCloseTo(4 + (1 - 10.8 / 11.6) * 52, 6) // 7,59
    expect(p0.y).toBeGreaterThan(p1.y) // mayor valor = más arriba (y menor)
  })
  it('un solo punto va al centro y una serie plana no divide por cero', () => {
    expect(puntosSerie([5], 100, 60)[0].x).toBe(50)
    const plana = puntosSerie([7, 7, 7])
    expect(plana.every((p) => Number.isFinite(p.y))).toBe(true)
  })
  it('trazos SVG', () => {
    const pts = [{ x: 0, y: 10 }, { x: 50, y: 20 }]
    expect(trazoLinea(pts)).toBe('M0.00,10.00 L50.00,20.00')
    expect(trazoArea(pts, 60)).toBe('M0.00,10.00 L50.00,20.00 L50.00,60 L0.00,60 Z')
    expect(trazoArea([])).toBe('')
  })
})

describe('variacion', () => {
  it('compara el último valor con el anterior', () => {
    expect(variacion([100, 110])).toEqual({ absoluta: 10, pct: 10 })
    expect(variacion([200, 150]).pct).toBeCloseTo(-25)
  })
  it('sin dos puntos no hay variación', () => {
    expect(variacion([100])).toBeNull()
  })
})
