import { describe, expect, it } from 'vitest'
import { MARCAS_FINANCIERAS_CO, contraste, marcaDeEntidad, marcaLegible } from '../lib/entidadesFinancierasCO'

describe('Colores de marca de los bancos: el texto siempre se lee', () => {
  it('toda marca queda con un contraste de al menos 5,5:1 entre su texto y su fondo', () => {
    for (const [nombre, marca] of Object.entries(MARCAS_FINANCIERAS_CO)) {
      const c = marcaLegible(marca)
      expect(contraste(c.fg, c.bg), nombre).toBeGreaterThanOrEqual(5.5)
    }
  })

  it('lo que ya se leía bien no se toca (Bancolombia, BBVA)', () => {
    for (const n of ['Bancolombia', 'BBVA Colombia']) {
      expect(marcaLegible(MARCAS_FINANCIERAS_CO[n])).toEqual(MARCAS_FINANCIERAS_CO[n])
    }
  })

  it('un rojo con texto blanco se oscurece pero sigue siendo rojo', () => {
    const original = MARCAS_FINANCIERAS_CO.Davivienda
    const c = marcaDeEntidad('Davivienda Ahorros')
    expect(c.bg).not.toBe(original.bg)
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(c.bg.slice(i, i + 2), 16))
    expect(r).toBeGreaterThan(g * 2)
    expect(r).toBeGreaterThan(b * 2)
    expect(c.fg).toBe(original.fg)
  })

  it('un nombre desconocido usa la marca por defecto, también legible', () => {
    const c = marcaDeEntidad('Mi cuenta rara')
    expect(contraste(c.fg, c.bg)).toBeGreaterThanOrEqual(5.5)
  })
})
