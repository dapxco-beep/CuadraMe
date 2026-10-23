// Presentación de la tarjeta como deuda: nunca saldo con signo ni «+». Datos inventados.
import { describe, expect, it } from 'vitest'
import { resumenDeuda } from '../lib/deudaTarjeta'

const fmt = (v) => `$${Math.round(v).toLocaleString('es-CO')}`

describe('resumenDeuda', () => {
  it('deuda con cupo: Debes · Cupo disponible y uso', () => {
    const r = resumenDeuda({ saldo: -800000, cupo: 3000000 }, fmt)
    expect(r.estado).toBe('deuda')
    expect(r.linea).toBe('Debes $800.000 · Cupo disponible $2.200.000')
    expect(r.cupo).toBe('$3.000.000')
    expect(Math.round(r.usoPct)).toBe(27)
    expect(r.excedido).toBeNull()
  })
  it('saldo positivo: Saldo a favor, sin cupo disponible ni signo', () => {
    const r = resumenDeuda({ saldo: 50000, cupo: 3000000 }, fmt)
    expect(r.estado).toBe('a_favor')
    expect(r.linea).toBe('Saldo a favor $50.000')
    expect(r.linea).not.toMatch(/[+-]/)
  })
  it('sin cupo no inventa cupo, disponible ni barra', () => {
    const r = resumenDeuda({ saldo: -120000 }, fmt)
    expect(r.linea).toBe('Debes $120.000')
    expect(r.cupo).toBeNull()
    expect(r.disponible).toBeNull()
    expect(r.usoPct).toBeNull()
    expect(resumenDeuda({ saldo: -1, cupo: 0 }, fmt).cupo).toBeNull()
  })
  it('cupo excedido: disponible $0, barra al 100 % y cuánto se pasó', () => {
    const r = resumenDeuda({ saldo: -3200000, cupo: 3000000 }, fmt)
    expect(r.disponible).toBe('$0')
    expect(r.usoPct).toBe(100)
    expect(r.excedido).toBe('$200.000')
  })
  it('sin deuda: al día; sin cupo pero con disponible del servidor lo deduce', () => {
    expect(resumenDeuda({ saldo: 0 }, fmt).estado).toBe('al_dia')
    const r = resumenDeuda({ saldo: -800000, disponible: 2200000 }, fmt)
    expect(r.cupo).toBe('$3.000.000')
  })
  it('entrada vacía o saldo basura no rompe', () => {
    expect(resumenDeuda(undefined, fmt).estado).toBe('al_dia')
    expect(resumenDeuda({ saldo: 'x' }, fmt).monto).toBe('$0')
  })
})
