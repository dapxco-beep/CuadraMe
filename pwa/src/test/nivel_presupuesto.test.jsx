import { describe, it, expect } from 'vitest'
import { nivelPresupuesto } from '../screens/Presupuesto'

const base = { alerta_pct: 80, pct: 10, pctReal: 10 }

describe('Nivel de un presupuesto', () => {
  it('excedido, ojo y va bien', () => {
    expect(nivelPresupuesto({ ...base, pct: 100, pctReal: 130 })).toBe(0)
    expect(nivelPresupuesto({ ...base, pct: 85, pctReal: 85 })).toBe(1)
    expect(nivelPresupuesto(base)).toBe(2)
  })

  it('la proyección también cuenta: en riesgo es «ojo» y excedido pesa más que el gasto actual', () => {
    expect(nivelPresupuesto({ ...base, proy: { estado: 'en_riesgo' } })).toBe(1)
    expect(nivelPresupuesto({ ...base, proy: { estado: 'excedido' } })).toBe(0)
    expect(nivelPresupuesto({ ...base, proy: { estado: 'en_camino' } })).toBe(2)
  })

  it('ordena primero lo que pide atención', () => {
    const lista = [{ ...base, id: 'a' }, { ...base, id: 'b', pct: 100, pctReal: 120 }, { ...base, id: 'c', pct: 85, pctReal: 85 }]
    const orden = [...lista].sort((x, y) => nivelPresupuesto(x) - nivelPresupuesto(y) || y.pctReal - x.pctReal).map((p) => p.id)
    expect(orden).toEqual(['b', 'c', 'a'])
  })
})
