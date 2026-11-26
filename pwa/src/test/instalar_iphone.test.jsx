import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const primer = vi.hoisted(() => ({ dispositivo: 'ios', instalada: false }))
vi.mock('../lib/primerUso', async (orig) => ({
  ...(await orig()),
  detectarDispositivo: () => primer.dispositivo,
  estaInstalada: () => primer.instalada,
}))

import AvisoInstalar from '../components/AvisoInstalar'
import { abrirMenuCompartir, avisoInstalarCerrado, cerrarAvisoInstalar, esNavegadorIntegrado } from '../lib/instalarIphone'

const SAFARI = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
const INSTAGRAM = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 300.0'
const WEBVIEW = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'

beforeEach(() => {
  primer.dispositivo = 'ios'
  primer.instalada = false
  window.localStorage.clear()
})
afterEach(() => {
  delete navigator.share
})

describe('navegador integrado', () => {
  it('distingue Safari de Instagram y de una vista web sin «Safari/»', () => {
    expect(esNavegadorIntegrado(SAFARI)).toBe(false)
    expect(esNavegadorIntegrado(INSTAGRAM)).toBe(true)
    expect(esNavegadorIntegrado(WEBVIEW)).toBe(true)
    expect(esNavegadorIntegrado('Mozilla/5.0 (Linux; Android 14) Chrome/120 Mobile Safari/537.36')).toBe(false)
  })
})

describe('menú de compartir', () => {
  it('sin navigator.share dice que no está disponible', async () => {
    expect(await abrirMenuCompartir('https://x')).toBe('no-disponible')
  })
  it('abre el menú, y si la persona lo cancela no es un error', async () => {
    navigator.share = vi.fn().mockResolvedValue()
    expect(await abrirMenuCompartir('https://x')).toBe('abierto')
    navigator.share = vi.fn().mockRejectedValue(Object.assign(new Error('x'), { name: 'AbortError' }))
    expect(await abrirMenuCompartir('https://x')).toBe('cancelado')
  })
})

describe('aviso para instalar en Inicio', () => {
  it('en iPhone «Instalar» abre el menú de compartir y explica qué tocar', async () => {
    navigator.share = vi.fn().mockResolvedValue()
    render(<AvisoInstalar />)
    fireEvent.click(screen.getByTestId('instalar-ahora'))
    await waitFor(() => expect(navigator.share).toHaveBeenCalledTimes(1))
    expect(await screen.findByTestId('pista-compartir')).toHaveTextContent('Añadir a pantalla de inicio')
  })

  it('si el iPhone no tiene menú de compartir abre la guía con pasos', async () => {
    render(<AvisoInstalar />)
    fireEvent.click(screen.getByTestId('instalar-ahora'))
    expect(await screen.findByTestId('guia-instalar')).toBeInTheDocument()
  })

  it('no sale en computador, ni si ya está instalada, ni después de cerrarlo (14 días)', () => {
    primer.dispositivo = 'otro'
    const { unmount } = render(<AvisoInstalar />)
    expect(screen.queryByTestId('aviso-instalar')).toBeNull()
    unmount()

    primer.dispositivo = 'ios'
    primer.instalada = true
    const dos = render(<AvisoInstalar />)
    expect(screen.queryByTestId('aviso-instalar')).toBeNull()
    dos.unmount()

    primer.instalada = false
    render(<AvisoInstalar />)
    fireEvent.click(screen.getByLabelText('Cerrar este aviso'))
    expect(screen.queryByTestId('aviso-instalar')).toBeNull()
    expect(avisoInstalarCerrado()).toBe(true)
    expect(avisoInstalarCerrado(Date.now() + 15 * 86400000)).toBe(false)
  })

  it('recuerda cerrarlo aunque se recargue', () => {
    cerrarAvisoInstalar()
    render(<AvisoInstalar />)
    expect(screen.queryByTestId('aviso-instalar')).toBeNull()
  })
})
