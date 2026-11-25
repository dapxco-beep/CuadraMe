import { describe, it, expect, vi, beforeEach } from 'vitest'
import { anotarPantalla, reiniciarVistas, rutaAnonima } from '../lib/usoPantallas'

describe('Medición anónima de uso', () => {
  beforeEach(() => reiniciarVistas())

  it('solo conserva el nombre de la pantalla y la pestaña', () => {
    expect(rutaAnonima('/presupuesto', '?tab=fijos')).toBe('/presupuesto?tab=fijos')
    expect(rutaAnonima('/Informes/', '?tab=Gastos&mes=2026-10&desde=2026-01-01')).toBe('/informes?tab=gastos')
    expect(rutaAnonima('/', '')).toBe('/')
  })

  it('quita identificadores y nunca deja pasar datos de la dirección', () => {
    expect(rutaAnonima('/movimientos/3f2a9c1e-1111-2222-3333-444455556666', '')).toBe('/movimientos/:id')
    expect(rutaAnonima('/hogares/123456/gasto', '?token=secreto')).toBe('/hogares/:id/gasto')
    expect(rutaAnonima('/c/abcdef0123456789abcdef', '')).toBe('/c/:id')
  })

  it('avisa una sola vez por pantalla y por sesión', () => {
    const cliente = { usoPantalla: vi.fn().mockResolvedValue({}) }
    expect(anotarPantalla('/informes', '?tab=gastos', cliente)).toBe(true)
    expect(anotarPantalla('/informes', '?tab=gastos', cliente)).toBe(false)
    expect(anotarPantalla('/informes', '?tab=dias', cliente)).toBe(true)
    expect(cliente.usoPantalla).toHaveBeenCalledTimes(2)
    expect(cliente.usoPantalla).toHaveBeenCalledWith('/informes?tab=gastos')
  })

  it('un fallo de red no rompe nada', () => {
    const cliente = { usoPantalla: vi.fn().mockRejectedValue(new Error('sin red')) }
    expect(() => anotarPantalla('/metas', '', cliente)).not.toThrow()
  })
})
