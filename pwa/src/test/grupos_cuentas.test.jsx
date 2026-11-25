import { describe, it, expect } from 'vitest'
import { agruparCuentas, subtotalGrupo } from '../lib/gruposCuentas'

const C = (id, tipo, saldo, moneda = 'COP') => ({ id, tipo, saldo, moneda })

describe('Grupos de cuentas', () => {
  const lista = [C('a', 'ahorro', 1000), C('b', 'credito', -500), C('c', 'efectivo', 200), C('d', 'inversion', 5000)]

  it('separa lo que tienes, lo que debes y lo invertido, conservando el orden', () => {
    const g = agruparCuentas(lista)
    expect(g.map((x) => x.id)).toEqual(['cuentas', 'tarjetas', 'inversion'])
    expect(g[0].items.map((c) => c.id)).toEqual(['a', 'c'])
  })

  it('no muestra grupos vacíos', () => {
    expect(agruparCuentas([C('a', 'ahorro', 1)]).map((x) => x.id)).toEqual(['cuentas'])
    expect(agruparCuentas([])).toEqual([])
  })

  it('suma los saldos del grupo solo en pesos', () => {
    expect(subtotalGrupo([C('a', 'ahorro', 1000), C('c', 'efectivo', 200)])).toBe(1200)
    expect(subtotalGrupo([C('x', 'ahorro', 50, 'USD')])).toBeNull()
    expect(subtotalGrupo([C('x', 'ahorro', 50, 'USD'), C('y', 'ahorro', 70)])).toBe(70)
  })
})
