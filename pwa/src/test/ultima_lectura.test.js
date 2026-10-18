import { describe, it, expect } from 'vitest'
import { textoUltimaLectura, SIN_CORREOS_NUEVOS } from '../lib/carriles'

describe('textoUltimaLectura', () => {
  it('resume la lectura con cifras', () => {
    expect(textoUltimaLectura({ leidos: 12, desde: '2026-10-15', nuevos: 2, ya_registrados: 9, ignorados: 0, avisos_descartados: 1 }))
      .toBe('Última lectura de movimientos: 12 correos desde el 15 oct → 2 nuevos, 9 ya registrados, 1 aviso descartado')
  })
  it('con 0 correos dos veces seguidas avisa claro', () => {
    expect(textoUltimaLectura({ leidos: 0, desde: '2026-10-15', ceros_seguidos: 2 })).toBe(SIN_CORREOS_NUEVOS)
    expect(textoUltimaLectura({ leidos: 0, desde: '2026-10-15', ceros_seguidos: 1 })).toMatch(/no devolvió correos/)
  })
  it('sin lectura no muestra nada', () => {
    expect(textoUltimaLectura(null)).toBeNull()
  })
})
