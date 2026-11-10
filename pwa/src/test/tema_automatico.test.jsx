import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, act } from '@testing-library/react'
import { ThemeProvider } from '../lib/ThemeContext'

// matchMedia falso que deja disparar el cambio del sistema.
function simularSistema(oscuro) {
  const oyentes = new Set()
  const mq = {
    matches: oscuro,
    media: '(prefers-color-scheme: dark)',
    addEventListener: (_, f) => oyentes.add(f),
    removeEventListener: (_, f) => oyentes.delete(f),
  }
  window.matchMedia = vi.fn(() => mq)
  return (nuevo) => {
    mq.matches = nuevo
    oyentes.forEach((f) => f({ matches: nuevo }))
  }
}

afterEach(() => {
  delete window.matchMedia
  localStorage.clear()
  vi.useRealTimers()
})

describe('modo automático', () => {
  it('sigue el sistema aunque la hora diga lo contrario', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 10, 9, 23, 0)) // de noche, pero el sistema pide claro
    simularSistema(false)
    render(<ThemeProvider><div /></ThemeProvider>)
    expect(document.documentElement.dataset.theme).toBe('calido')
  })

  it('cambia en vivo cuando el sistema cambia', () => {
    const cambiar = simularSistema(false)
    render(<ThemeProvider><div /></ThemeProvider>)
    expect(document.documentElement.dataset.theme).toBe('calido')
    act(() => cambiar(true))
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('sin matchMedia usa la hora como respaldo', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 10, 9, 22, 0))
    render(<ThemeProvider><div /></ThemeProvider>)
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('una elección manual no depende del sistema', () => {
    localStorage.setItem('findp_theme', 'calido')
    simularSistema(true)
    render(<ThemeProvider><div /></ThemeProvider>)
    expect(document.documentElement.dataset.theme).toBe('calido')
  })
})
