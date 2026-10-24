import { describe, expect, it } from 'vitest'
import manifest from '../../public/manifest.json'

describe('manifest PWA', () => {
  it('tiene accesos directos de mantener pulsado el ícono, con rutas internas', () => {
    expect(manifest.shortcuts.length).toBeGreaterThanOrEqual(3)
    for (const s of manifest.shortcuts) {
      expect(s.name).toBeTruthy()
      expect(s.url.startsWith('/')).toBe(true)
    }
  })
})
