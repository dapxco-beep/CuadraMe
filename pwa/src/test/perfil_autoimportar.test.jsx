import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
const auth = vi.hoisted(() => ({ usuario: { id: 'u-auto', email: 'a@test.com', nombre: 'Ana' } }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ iconoDe: () => '💳' }) }))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import Perfil from '../screens/Perfil'

const montar = () =>
  render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter>
          <Perfil />
        </MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  localStorage.setItem('cuadrame:inicio-secciones', JSON.stringify({ 'perfil-avisos': true })) // «Avisos y conexiones» abierta
  Object.assign(api, {
    apiKey: vi.fn().mockResolvedValue({ api_key: 'k' }),
    confianzaAutoimport: vi.fn().mockResolvedValue({ confianza_autoimport: 0.8, activo: false }),
    actualizarAutoimportarExtractos: vi.fn().mockResolvedValue({ activo: true }),
    actualizarConfianzaAutoimport: vi.fn().mockResolvedValue({}),
  })
})

describe('Perfil: «Anotar solo lo que reconozco con seguridad»', () => {
  it('viene apagado, sin el deslizador, y con una sola petición para saberlo', async () => {
    montar()
    const interruptor = await screen.findByTestId('switch-autoimportar')
    await waitFor(() => expect(interruptor).toBeEnabled())
    expect(interruptor).toHaveAttribute('aria-checked', 'false')
    expect(screen.queryByText('¿Qué tan seguro debo estar?')).toBeNull()
    expect(api.confianzaAutoimport).toHaveBeenCalledTimes(1)
  })

  it('al encenderlo se guarda y aparece el deslizador de qué tan seguro', async () => {
    const user = userEvent.setup()
    montar()
    const interruptor = await screen.findByTestId('switch-autoimportar')
    await waitFor(() => expect(interruptor).toBeEnabled())
    await user.click(interruptor)
    await waitFor(() => expect(api.actualizarAutoimportarExtractos).toHaveBeenCalledWith(true))
    expect(interruptor).toHaveAttribute('aria-checked', 'true')
    expect(await screen.findByText('¿Qué tan seguro debo estar?')).toBeInTheDocument()
  })

  it('si no se puede guardar, el interruptor vuelve a como estaba', async () => {
    const user = userEvent.setup()
    api.actualizarAutoimportarExtractos = vi.fn().mockRejectedValue(new Error('sin red'))
    montar()
    const interruptor = await screen.findByTestId('switch-autoimportar')
    await waitFor(() => expect(interruptor).toBeEnabled())
    await user.click(interruptor)
    await waitFor(() => expect(api.actualizarAutoimportarExtractos).toHaveBeenCalled())
    await waitFor(() => expect(interruptor).toHaveAttribute('aria-checked', 'false'))
  })

  it('si ya estaba encendido llega encendido', async () => {
    api.confianzaAutoimport = vi.fn().mockResolvedValue({ confianza_autoimport: 0.75, activo: true })
    montar()
    const interruptor = await screen.findByTestId('switch-autoimportar')
    await waitFor(() => expect(interruptor).toHaveAttribute('aria-checked', 'true'))
    expect(await screen.findByText('¿Qué tan seguro debo estar?')).toBeInTheDocument()
  })
})
