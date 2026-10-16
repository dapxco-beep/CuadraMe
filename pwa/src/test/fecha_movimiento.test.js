import { describe, it, expect } from 'vitest'
import { fechaHoraMovimiento, horaCorta, tieneHora } from '../lib/fechaMovimiento'

describe('fechaHoraMovimiento', () => {
  it('muestra día y hora cuando la hora es real', () => {
    const t = fechaHoraMovimiento('2026-10-08T16:30:00')
    expect(t).toMatch(/^jue 8 oct · 4:30/)
    expect(t).not.toMatch(/\bde\b/)
  })
  it('no inventa hora cuando es medianoche o mediodía de relleno', () => {
    expect(fechaHoraMovimiento('2026-10-08T00:00:00')).toBe('jue 8 oct')
    expect(horaCorta('2026-10-08T12:00:00')).toBe('')
    expect(tieneHora('2026-10-08T00:00:00')).toBe(false)
  })
  it('una fecha solo con día no se corre un día atrás', () => {
    expect(fechaHoraMovimiento('2026-10-08')).toBe('jue 8 oct')
  })
  it('entrada inválida devuelve vacío', () => {
    expect(fechaHoraMovimiento('')).toBe('')
    expect(fechaHoraMovimiento('xx')).toBe('')
  })
})
