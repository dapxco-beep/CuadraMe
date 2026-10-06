import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../components/PantallaBloqueo', () => ({
  default: () => <div role="dialog" aria-label="App bloqueada">Ingresa tu PIN</div>,
}))
vi.mock('../lib/supabase', () => ({ supabase: { auth: { getSession: vi.fn() } } }))

import { ArbolConBloqueo } from '../App'

function Formulario() {
  return <input aria-label="Monto" />
}

describe('Bloqueo con PIN como overlay', () => {
  it('conserva el formulario a medias al bloquear y al desbloquear', async () => {
    const { rerender } = render(
      <ArbolConBloqueo bloqueado={false}>
        <Formulario />
      </ArbolConBloqueo>
    )
    await userEvent.type(screen.getByLabelText('Monto'), '45000')

    rerender(
      <ArbolConBloqueo bloqueado>
        <Formulario />
      </ArbolConBloqueo>
    )
    expect(screen.getByRole('dialog', { name: 'App bloqueada' })).toBeInTheDocument()
    const arbol = screen.getByTestId('arbol-app')
    expect(arbol).toHaveAttribute('aria-hidden', 'true')
    expect(arbol).toHaveAttribute('inert')
    // el campo sigue montado con lo que el usuario había escrito
    expect(screen.getByLabelText('Monto', { hidden: true })).toHaveValue('45000')

    rerender(
      <ArbolConBloqueo bloqueado={false}>
        <Formulario />
      </ArbolConBloqueo>
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Monto')).toHaveValue('45000')
    expect(screen.getByTestId('arbol-app')).not.toHaveAttribute('inert')
  })

  it('al abrir la app ya bloqueada no se monta nada detrás del candado', () => {
    render(
      <ArbolConBloqueo bloqueado>
        <Formulario />
      </ArbolConBloqueo>
    )
    expect(screen.getByRole('dialog', { name: 'App bloqueada' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Monto', { hidden: true })).not.toBeInTheDocument()
  })
})
