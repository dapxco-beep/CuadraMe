import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { generar } from '../../scripts/generar-legales-estaticos.mjs'

const leer = (n) => readFileSync(resolve(process.cwd(), 'public', n), 'utf8')

describe('páginas legales estáticas', () => {
  it('están al día con las pantallas React (si falla: npm run legales)', () => {
    for (const [nombre, html] of Object.entries(generar())) {
      expect(leer(nombre).replace(/\r\n/g, '\n')).toBe(html)
    }
  })

  it('la política trae las secciones que exige Google y no usa JS', () => {
    const h = leer('privacidad.html')
    expect(h).toContain('Uso de la información recibida de las APIs de Google')
    expect(h).toContain('Uso Limitado')
    expect(h).toContain('developers.google.com/terms/api-services-user-data-policy')
    expect(h).toContain('gmail.readonly')
    expect(h).toContain('BORRADOR PARA REVISIÓN DE ABOGADO')
    expect(h).toContain('Versión 1.1')
    expect(h).toContain('dapxco@gmail.com')
    expect(h).toContain('href="/"')
    expect(h).not.toMatch(/<script|className|\{'/)
  })

  it('los términos traen aviso, versión y contacto', () => {
    const h = leer('terminos.html')
    expect(h).toContain('Términos y Condiciones')
    expect(h).toContain('BORRADOR PARA REVISIÓN DE ABOGADO')
    expect(h).toContain('Versión 1.1')
    expect(h).toContain('dapxco@gmail.com')
    expect(h).not.toMatch(/<script|className|\{'/)
  })

  it('bienvenida enlaza ambas páginas', () => {
    const b = leer('bienvenida.html')
    expect(b).toContain('/privacidad.html')
    expect(b).toContain('/terminos.html')
  })
})
