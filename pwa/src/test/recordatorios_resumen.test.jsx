// Recordatorios descartables en Inicio y opt-in del resumen semanal por correo en Perfil.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({
  api: new Proxy(api, { get: (t, nombre) => t[nombre] ?? (() => Promise.resolve([])) }),
}))
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({ usuario: { id: 'u1', email: 'l@test.com', nombre: 'Laura' }, logout: vi.fn() }),
}))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import Recordatorios from '../components/Recordatorios'
import Perfil from '../screens/Perfil'

const LISTA = [
  { clave: 'tarjeta:c1:2026-10-09', tipo: 'tarjeta', titulo: 'Pagas Visa en 2 días', texto: 'Para no pagar intereses faltan $500.000.', ruta: '/cuentas' },
  { clave: 'presupuesto:Comida:2026-10', tipo: 'presupuesto', titulo: 'Comida: ya usaste el 85 %', texto: 'Llevas $40.000 de $47.000.', ruta: '/presupuesto' },
]

function montar(ui) {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  for (const k of Object.keys(api)) delete api[k]
})

describe('Recordatorios en Inicio', () => {
  it('muestra las tarjetas y al descartar una no vuelve (se recuerda en el dispositivo)', async () => {
    api.recordatorios = vi.fn().mockResolvedValue(LISTA)
    const { unmount } = montar(<Recordatorios />)
    expect(await screen.findByText('Pagas Visa en 2 días')).toBeInTheDocument()
    expect(screen.getByText('Comida: ya usaste el 85 %')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Descartar: Pagas Visa/ }))
    expect(screen.queryByText('Pagas Visa en 2 días')).not.toBeInTheDocument()
    expect(screen.getByText('Comida: ya usaste el 85 %')).toBeInTheDocument()

    unmount()
    montar(<Recordatorios />)
    expect(await screen.findByText('Comida: ya usaste el 85 %')).toBeInTheDocument()
    expect(screen.queryByText('Pagas Visa en 2 días')).not.toBeInTheDocument()
  })

  it('si el recordatorio cambia de situación (otra clave), vuelve a aparecer', async () => {
    localStorage.setItem('cuadrame:recordatorios-descartados', JSON.stringify(['tarjeta:c1:2026-09-09']))
    api.recordatorios = vi.fn().mockResolvedValue(LISTA)
    montar(<Recordatorios />)
    expect(await screen.findByText('Pagas Visa en 2 días')).toBeInTheDocument()
  })

  it('sin recordatorios, o si el servidor falla, no muestra nada', async () => {
    api.recordatorios = vi.fn().mockRejectedValue(new Error('caído'))
    const { container } = montar(<Recordatorios />)
    await waitFor(() => expect(api.recordatorios).toHaveBeenCalled())
    expect(container.querySelector('[data-testid="recordatorios"]')).toBeNull()
  })
})

describe('Perfil — resumen semanal por correo', () => {
  it('viene apagado y se activa con el interruptor (opt-in)', async () => {
    api.resumenPreferencias = vi.fn().mockResolvedValue({ correo: false, email: 'resumen@test.com' })
    api.guardarResumenPreferencias = vi.fn().mockResolvedValue({ ok: true, correo: true })
    localStorage.setItem('cuadrame:inicio-secciones', JSON.stringify({ 'perfil-seguridad': true, 'perfil-avisos': true })) // bloques del Perfil abiertos
    montar(<Perfil />)
    const interruptor = await screen.findByRole('switch', { name: /Resumen semanal por correo/ })
    await waitFor(() => expect(screen.getByText(/l@test\.com/)).toBeInTheDocument())
    expect(interruptor).toHaveAttribute('aria-checked', 'false')

    await userEvent.click(interruptor)
    expect(api.guardarResumenPreferencias).toHaveBeenCalledWith(true)
    await waitFor(() => expect(interruptor).toHaveAttribute('aria-checked', 'true'))
  })

  it('si guardar falla, el interruptor vuelve a su estado anterior', async () => {
    api.resumenPreferencias = vi.fn().mockResolvedValue({ correo: false, email: 'resumen@test.com' })
    api.guardarResumenPreferencias = vi.fn().mockRejectedValue(new Error('sin conexión'))
    localStorage.setItem('cuadrame:inicio-secciones', JSON.stringify({ 'perfil-seguridad': true, 'perfil-avisos': true })) // bloques del Perfil abiertos
    montar(<Perfil />)
    const interruptor = await screen.findByRole('switch', { name: /Resumen semanal por correo/ })
    await userEvent.click(interruptor)
    await waitFor(() => expect(interruptor).toHaveAttribute('aria-checked', 'false'))
  })
})
