import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup, configure } from '@testing-library/react'

// Con muchas pruebas en paralelo (o la máquina ocupada) 1 s de espera por defecto se queda corto.
configure({ asyncUtilTimeout: 5000 })

afterEach(cleanup)

// jsdom no implementa scrollIntoView ni matchMedia
window.HTMLElement.prototype.scrollIntoView = () => {}
window.matchMedia =
  window.matchMedia ||
  (() => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }))
