import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

vi.mock('../lib/AuthContext', () => ({ useAuth: () => ({ usuario: { id: 'u-inv' } }) }))
vi.mock('../lib/api', () => ({ api: {} }))

import InvitacionPerfil from '../components/InvitacionPerfil'
import { leerPerfilUso } from '../lib/modoSimple'

describe('Invitación a elegir cómo usar CuadraMe', () => {
  beforeEach(() => localStorage.clear())

  it('aparece una vez; elegir un perfil la quita y lo guarda', async () => {
    render(<InvitacionPerfil />)
    expect(screen.getByTestId('invitacion-perfil')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Quiero ahorrar' }))
    expect(leerPerfilUso('u-inv')).toBe('ahorro')
    expect(screen.queryByTestId('invitacion-perfil')).toBeNull()
  })

  it('«Ahora no» la oculta y no vuelve a insistir', async () => {
    const { unmount } = render(<InvitacionPerfil />)
    await userEvent.click(screen.getByRole('button', { name: 'Ahora no' }))
    expect(screen.queryByTestId('invitacion-perfil')).toBeNull()
    unmount()
    render(<InvitacionPerfil />)
    expect(screen.queryByTestId('invitacion-perfil')).toBeNull()
    expect(leerPerfilUso('u-inv')).toBeNull() // no eligió nada: el menú sigue en «Esencial» por defecto
  })

  it('no aparece si ya eligió antes', () => {
    localStorage.setItem('cuadrame:perfil-uso:u-inv', 'gastos')
    render(<InvitacionPerfil />)
    expect(screen.queryByTestId('invitacion-perfil')).toBeNull()
  })

  it('no aparece para quien ya tenía todas las funciones encendidas', () => {
    localStorage.setItem('cuadrame:modo-completo:u-inv', '1')
    render(<InvitacionPerfil />)
    expect(screen.queryByTestId('invitacion-perfil')).toBeNull()
  })
})
