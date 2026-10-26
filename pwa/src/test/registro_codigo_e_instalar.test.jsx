import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const auth = vi.hoisted(() => ({
  login: vi.fn(), registro: vi.fn(), confirmarCodigo: vi.fn(), reenviarCodigo: vi.fn(), loginConGoogle: vi.fn(), recuperarPassword: vi.fn(),
}))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => auth }))

import Login from '../screens/Login'
import GuiaInstalar from '../components/GuiaInstalar'
import { _simularEvento } from '../lib/instalarPwa'

const pintarLogin = () => render(<MemoryRouter><Login /></MemoryRouter>)

describe('Registro con código', () => {
  beforeEach(() => Object.values(auth).forEach((f) => f.mockReset()))

  async function registrar() {
    auth.registro.mockResolvedValue()
    pintarLogin()
    fireEvent.click(screen.getByText('¿No tienes cuenta? Regístrate'))
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Ana' } })
    fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'ana@correo.com' } })
    fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: 'claveSegura1' } })
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Crear cuenta' }))
    await screen.findByTestId('paso-codigo')
  }

  it('tras crear la cuenta pide el código y confirma con él', async () => {
    await registrar()
    expect(screen.getByRole('status')).toHaveTextContent('ana@correo.com')
    auth.confirmarCodigo.mockResolvedValue()
    fireEvent.change(screen.getByLabelText('Código del correo'), { target: { value: '12 34-56' } }) // solo deja números
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar y entrar' }))
    await waitFor(() => expect(auth.confirmarCodigo).toHaveBeenCalledWith('ana@correo.com', '123456'))
  })

  it('un código incorrecto muestra el error y deja reintentar o reenviar', async () => {
    await registrar()
    auth.confirmarCodigo.mockRejectedValue(new Error('El código no es correcto o ya venció'))
    fireEvent.change(screen.getByLabelText('Código del correo'), { target: { value: '000000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar y entrar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('código no es correcto')
    auth.reenviarCodigo.mockResolvedValue()
    fireEvent.click(screen.getByRole('button', { name: 'Reenviar código' }))
    await waitFor(() => expect(auth.reenviarCodigo).toHaveBeenCalledWith('ana@correo.com'))
  })

  it('«Cambiar el correo» vuelve al formulario', async () => {
    await registrar()
    fireEvent.click(screen.getByRole('button', { name: 'Cambiar el correo' }))
    expect(screen.getByLabelText('Correo')).toBeInTheDocument()
  })
})

describe('Instalar en Android con un toque', () => {
  it('muestra el botón solo cuando Chrome ya dejó instalar, y abre el cuadro de instalación', async () => {
    const prompt = vi.fn().mockResolvedValue()
    render(<GuiaInstalar dispositivo="android" onCerrar={() => {}} />)
    expect(screen.queryByTestId('instalar-un-toque')).toBeNull()
    act(() => _simularEvento({ prompt, userChoice: Promise.resolve({ outcome: 'accepted' }) }))
    fireEvent.click(await screen.findByTestId('instalar-un-toque'))
    await waitFor(() => expect(prompt).toHaveBeenCalledTimes(1))
  })

  it('en iPhone no ofrece el botón (Safari no lo permite): quedan los pasos', () => {
    act(() => _simularEvento({ prompt: vi.fn(), userChoice: Promise.resolve({ outcome: 'accepted' }) }))
    render(<GuiaInstalar dispositivo="ios" onCerrar={() => {}} />)
    expect(screen.queryByTestId('instalar-un-toque')).toBeNull()
    expect(screen.getByText(/Añadir a pantalla de inicio/)).toBeInTheDocument()
  })
})
