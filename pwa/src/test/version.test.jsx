import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import LineaVersion from '../components/LineaVersion'
import { fechaCompilacion, hayVersionNueva, textoVersion } from '../lib/version'

describe('version', () => {
  it('formatea la compilación y el texto de soporte', () => {
    expect(fechaCompilacion('')).toBe('')
    expect(textoVersion({ version: '1.0.0', build: '', commit: 'abc1234' })).toBe('CuadraMe 1.0.0 · abc1234')
    expect(textoVersion({ version: '1.0.0', build: '2026-10-14T19:26:00Z', commit: 'abc1234' })).toMatch(/^CuadraMe 1\.0\.0 · compilación \d+ oct 2026 \d\d:\d\d · abc1234$/)
  })

  it('detecta una compilación más nueva y no se alarma sin datos', () => {
    const act = { build: '2026-10-14T10:00:00Z', commit: 'aaa1111' }
    expect(hayVersionNueva({ build: '2026-10-14T12:00:00Z', commit: 'bbb2222' }, act)).toBe(true)
    expect(hayVersionNueva({ build: '2026-10-14T12:00:00Z', commit: 'aaa1111' }, act)).toBe(false)
    expect(hayVersionNueva({ build: '2026-10-14T09:00:00Z', commit: 'ccc3333' }, act)).toBe(false)
    expect(hayVersionNueva(null, act)).toBe(false)
    expect(hayVersionNueva({ build: '2026-10-14T12:00:00Z', commit: 'x' }, { build: '', commit: 'dev' })).toBe(false)
  })

  it('LineaVersion muestra la versión y el detalle tras 5 toques', async () => {
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ version: '1.0.0', commit: 'abc1234' }) })
    render(<LineaVersion />)
    const linea = screen.getByTestId('linea-version')
    expect(linea.textContent).toMatch(/^CuadraMe /)
    expect(screen.getByText('Copiar')).toBeTruthy()
    for (let i = 0; i < 5; i++) fireEvent.click(linea)
    await waitFor(() => expect(screen.getByText(/Servidor: 1\.0\.0 · abc1234/)).toBeTruthy())
    expect(screen.getByText(/Service worker:/)).toBeTruthy()
  })
})
