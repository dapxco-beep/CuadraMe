import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
const auth = vi.hoisted(() => ({ usuario: { id: 'u-lg', email: 'a@test.com', nombre: 'Ana' } }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ iconoDe: () => '💳' }) }))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import Perfil from '../screens/Perfil'

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  document.documentElement.style.fontSize = ''
  localStorage.setItem('cuadrame:inicio-secciones', JSON.stringify({ 'perfil-preferencias': true }))
  Object.assign(api, {
    apiKey: vi.fn().mockResolvedValue({ api_key: 'k' }),
    confianzaAutoimport: vi.fn().mockResolvedValue({ confianza_autoimport: 0.8, activo: false }),
  })
})

describe('Perfil: Letra grande', () => {
  it('el interruptor sube la letra, se guarda y se puede apagar', async () => {
    render(
      <ThemeProvider><DialogosProvider><MemoryRouter><Perfil /></MemoryRouter></DialogosProvider></ThemeProvider>
    )
    const sw = await screen.findByTestId('switch-letra-grande')
    expect(sw).toHaveAttribute('aria-checked', 'false')
    await userEvent.click(sw)
    expect(sw).toHaveAttribute('aria-checked', 'true')
    expect(document.documentElement.style.fontSize).toBe('112.5%')
    expect(localStorage.getItem('cuadrame:letra-grande')).toBe('1')
    await userEvent.click(sw)
    expect(document.documentElement.style.fontSize).toBe('')
  })
})
