import { describe, it, expect } from 'vitest'
import { estadoPorScore } from '../lib/saludFinanciera'
import { normalizarPaneles } from '../lib/panelesInforme'
import { repartirMapa } from '../components/informe/MapaCategorias'
import { obtenerHallazgos } from '../components/informe/LoQueLlamaLaAtencion'
import { proyeccionMes } from '../components/informe/HeroGasto'

const fmt = (n) => `$${n}`

describe('Cuadri según la salud financiera', () => {
  it('cada puntaje tiene un estado, de radiante a crítico', () => {
    expect([95, 80, 60, 45, 30, 5].map(estadoPorScore)).toEqual(['radiante', 'bien', 'regular', 'cansado', 'mal', 'critico'])
  })
})

describe('Paneles personalizables de Informes', () => {
  it('sin nada guardado muestra todos en el orden original', () => {
    const p = normalizarPaneles(null)
    expect(p.orden[0]).toBe('resumen')
    expect(p.ocultos).toEqual([])
  })
  it('descarta paneles que ya no existen y agrega los nuevos al final', () => {
    const p = normalizarPaneles({ orden: ['dia', 'inexistente', 'resumen'], ocultos: ['comercios', 'otro'] })
    expect(p.orden.slice(0, 2)).toEqual(['dia', 'resumen'])
    expect(p.orden).toContain('mes_a_mes')
    expect(p.orden).not.toContain('inexistente')
    expect(p.ocultos).toEqual(['comercios'])
  })
})

describe('Paneles unidos: lo que la persona ya tenía guardado se traduce', () => {
  it('los cinco paneles viejos pasan a dos y respetan el orden', () => {
    const p = normalizarPaneles({ orden: ['resumen', 'historial', 'ingresos', 'evolucion', 'mi_evolucion'], ocultos: [] })
    expect(p.orden.filter((id) => ['mes_a_mes', 'ingresos'].includes(id))).toEqual(['mes_a_mes', 'ingresos'])
    expect(p.orden).not.toContain('historial')
    expect(p.orden).not.toContain('mi_evolucion')
  })
  it('un panel unido se oculta solo si ya tenía ocultas todas sus partes', () => {
    const orden = ['historial', 'evolucion', 'ingresos', 'mi_evolucion']
    expect(normalizarPaneles({ orden, ocultos: ['historial', 'evolucion'] }).ocultos).toEqual(['mes_a_mes'])
    expect(normalizarPaneles({ orden, ocultos: ['historial'] }).ocultos).toEqual([])
    expect(normalizarPaneles({ orden, ocultos: ['mi_evolucion'] }).ocultos).toEqual([])
    expect(normalizarPaneles({ orden, ocultos: ['ingresos', 'mi_evolucion'] }).ocultos).toEqual(['ingresos'])
  })
})

describe('Mapa de categorías', () => {
  it('reparte todo el espacio: la suma de las áreas es el 100 % y nada se sale', () => {
    const r = repartirMapa([{ v: 50 }, { v: 25 }, { v: 15 }, { v: 10 }])
    const area = r.reduce((s, x) => s + (x.w * x.h) / 100, 0)
    expect(Math.round(area)).toBe(100)
    expect(r.every((x) => x.x >= 0 && x.y >= 0 && x.x + x.w <= 100.001 && x.y + x.h <= 100.001)).toBe(true)
    expect(r.length).toBe(4)
  })
  it('el área es proporcional al gasto', () => {
    const r = repartirMapa([{ v: 75 }, { v: 25 }])
    const [a, b] = r.map((x) => (x.w * x.h) / 100)
    expect(Math.round(a / b)).toBe(3)
  })
})

describe('Lo que llama la atención', () => {
  const informe = {
    ingresos: 1_000_000, ahorro: 300_000,
    categorias: [
      { categoria: 'Comida', monto: 450_000, pct: 60, anterior: 200_000, variacion_pct: 125 },
      { categoria: 'Ocio', monto: 50_000, pct: 10, anterior: 200_000, variacion_pct: -75 },
    ],
    comercios: [{ nombre: 'Éxito', num: 4, monto: 300_000 }],
  }
  it('detecta lo que subió, lo que bajó, lo que pesa y el ahorro', () => {
    const ids = obtenerHallazgos(informe, fmt).map((h) => h.id)
    expect(ids).toEqual(expect.arrayContaining(['sube', 'baja', 'peso', 'ahorro']))
  })
  it('avisa cuando se gastó más de lo que entró', () => {
    const h = obtenerHallazgos({ ...informe, ahorro: -50_000 }, fmt).find((x) => x.id === 'ahorro')
    expect(h.titulo).toMatch(/más de lo que entró/)
  })
  it('sin cambios grandes no inventa nada', () => {
    const h = obtenerHallazgos({ ingresos: 0, ahorro: 0, categorias: [{ categoria: 'Comida', monto: 1000, pct: 20, anterior: 1000, variacion_pct: 0 }], comercios: [] }, fmt)
    expect(h).toEqual([])
  })
})

describe('Proyección del mes', () => {
  it('al mismo ritmo hasta el último día', () => {
    expect(proyeccionMes(300_000, new Date(2026, 5, 10))).toBe(900_000) // junio tiene 30 días
  })
  it('no proyecta en los primeros días ni el último', () => {
    expect(proyeccionMes(300_000, new Date(2026, 5, 2))).toBeNull()
    expect(proyeccionMes(300_000, new Date(2026, 5, 30))).toBeNull()
    expect(proyeccionMes(0, new Date(2026, 5, 10))).toBeNull()
  })
})
