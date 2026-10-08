import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup, configure } from '@testing-library/react'

// Con muchas pruebas en paralelo (o la máquina ocupada) 1 s de espera por defecto se queda corto.
configure({ asyncUtilTimeout: 5000 })

afterEach(cleanup)

// En el contexto aislado de vmThreads jsdom no expone crypto.subtle; lo tomamos del webcrypto de Node.
if (!globalThis.crypto?.subtle) {
  const { webcrypto } = await import('node:crypto')
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })
}

// jsdom no implementa scrollIntoView ni matchMedia
window.HTMLElement.prototype.scrollIntoView = () => {}
window.matchMedia =
  window.matchMedia ||
  (() => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }))
