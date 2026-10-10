// Estable como app nativa: sin zoom por pellizco ni doble toque, sin zoom automático de iOS en
// campos, sin scroll horizontal. (La verificación de pantallas a 360 y 390 px está en
// scripts/verificar-ancho.mjs: necesita un navegador real.)
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { bloquearZoomPellizco } from '../lib/estabilidadVista'

const raiz = process.cwd()
const html = readFileSync(`${raiz}/index.html`, 'utf8')
const css = readFileSync(`${raiz}/src/index.css`, 'utf8')

describe('viewport y CSS base', () => {
  it('el meta viewport fija la escala y cubre la zona segura', () => {
    const meta = /<meta name="viewport" content="([^"]+)"/.exec(html)[1]
    expect(meta).toContain('width=device-width')
    expect(meta).toContain('maximum-scale=1')
    expect(meta).toContain('user-scalable=no')
    expect(meta).toContain('viewport-fit=cover')
  })

  it('el CSS evita el zoom por doble toque y el reescalado de texto', () => {
    expect(css).toMatch(/touch-action:\s*manipulation/)
    expect(css).toMatch(/-webkit-text-size-adjust:\s*100%/)
    expect(css).toMatch(/overflow-x:\s*(hidden|clip)/)
  })

  it('en el móvil los campos miden 16 px (iOS no hace zoom al enfocarlos)', () => {
    const bloque = /@media \(max-width: 767px\) \{([\s\S]*?)\n\}/.exec(css)[1]
    expect(bloque).toMatch(/select/)
    expect(bloque).toMatch(/textarea/)
    expect(bloque).toMatch(/font-size:\s*16px/)
  })

  it('no fija el tamaño de texto de <html> (se respeta el del sistema)', () => {
    expect(css).not.toMatch(/html\s*\{[^}]*font-size:\s*\d+px/)
  })
})

describe('bloquearZoomPellizco', () => {
  function evento(tipo, extra = {}) {
    const e = new Event(tipo, { cancelable: true, bubbles: true })
    Object.assign(e, extra)
    return e
  }

  it('cancela el gesto de pellizco de Safari y el toque de dos dedos', () => {
    const quitar = bloquearZoomPellizco(document)
    const g = evento('gesturestart')
    document.dispatchEvent(g)
    expect(g.defaultPrevented).toBe(true)
    const dos = evento('touchmove', { touches: [{}, {}] })
    document.dispatchEvent(dos)
    expect(dos.defaultPrevented).toBe(true)
    quitar()
  })

  it('no toca el scroll de un dedo', () => {
    const quitar = bloquearZoomPellizco(document)
    const uno = evento('touchmove', { touches: [{}], scale: 1 })
    document.dispatchEvent(uno)
    expect(uno.defaultPrevented).toBe(false)
    quitar()
  })

  it('devuelve cómo deshacerlo', () => {
    const quitar = bloquearZoomPellizco(document)
    quitar()
    const g = evento('gesturestart')
    document.dispatchEvent(g)
    expect(g.defaultPrevented).toBe(false)
  })
})
