import { describe, expect, it } from 'vitest'
import { FRASES_DECISION, decisionVisible } from '../lib/decisionesAutoarreglo'

const JERGA = /dudosa|huella|fingerprint/i

describe('decisiones en lenguaje claro', () => {
  it('cada tipo conocido tiene frase amable y botón, con plurales', () => {
    expect(decisionVisible({ tipo: 'dudosas', cantidad: 1, texto: 'x', accion: 'Revisarlos' })).toMatchObject({
      texto: 'Tengo una duda con 1 movimiento. ¿Los revisamos?', accion: 'Revisar', ruta: '/sincronizacion',
    })
    expect(decisionVisible({ tipo: 'dudosas', cantidad: 7 }).texto).toBe('Tengo una duda con 7 movimientos. ¿Los revisamos?')
    expect(decisionVisible({ tipo: 'clave_pdf', cantidad: 2, ruta: '/correos' })).toMatchObject({ accion: 'Poner la clave', ruta: '/correos' })
    expect(decisionVisible({ tipo: 'clave_pdf', cantidad: 1 }).texto).toMatch(/1 extracto en PDF para poder leerlo/)
  })

  it('ninguna frase muestra jerga, con o sin cantidad', () => {
    for (const [tipo, f] of Object.entries(FRASES_DECISION)) {
      for (const n of [0, 1, 5]) expect(f.texto(n), `${tipo}/${n}`).not.toMatch(JERGA)
      expect(decisionVisible({ tipo, cantidad: 0 }).texto).not.toMatch(/\b0\b/)
    }
  })

  it('un tipo desconocido cae al texto y la acción del servidor', () => {
    expect(decisionVisible({ tipo: 'nuevo', cantidad: 3, texto: 'Algo nuevo.', accion: 'Ver', ruta: '/x' }))
      .toEqual({ clave: 'nuevo', texto: 'Algo nuevo.', accion: 'Ver', ruta: '/x', cantidad: 3 })
  })
})
