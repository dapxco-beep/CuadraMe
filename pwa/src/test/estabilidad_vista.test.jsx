// Vista estable SIN bloquear el zoom (WCAG 1.4.4): se puede ampliar con pellizco, no hay zoom automático de iOS en campos
// y no hay scroll horizontal. (La verificación de pantallas a 360 y 390 px está en scripts/verificar-ancho.mjs.)
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const raiz = process.cwd()
const html = readFileSync(`${raiz}/index.html`, 'utf8')
const css = readFileSync(`${raiz}/src/index.css`, 'utf8')
const main = readFileSync(`${raiz}/src/main.jsx`, 'utf8')

describe('viewport y CSS base', () => {
  it('el meta viewport NO bloquea el zoom y cubre la zona segura', () => {
    const meta = /<meta name="viewport" content="([^"]+)"/.exec(html)[1]
    expect(meta).toContain('width=device-width')
    expect(meta).toContain('viewport-fit=cover')
    expect(meta).not.toMatch(/user-scalable\s*=\s*(no|0)/)
    expect(meta).not.toMatch(/maximum-scale/)
    expect(meta).not.toMatch(/minimum-scale/)
  })

  it('no hay código que cancele el pellizco ni los gestos de zoom', () => {
    expect(main).not.toMatch(/bloquearZoom|gesturestart/)
    expect(css).not.toMatch(/touch-action:\s*(none|pan-x\s+pan-y)/)
  })

  it('el CSS evita solo el zoom por doble toque y el reescalado de texto', () => {
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
