// Perfil -> Privacidad y datos: descargar mis datos y borrar mi cuenta (Ley 1581).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  consentimientos: vi.fn(),
  historialConsentimientos: vi.fn(),
  guardarConsentimientos: vi.fn(),
  descargarMisDatos: vi.fn(),
  eliminarMiCuenta: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))

import { DialogosProvider } from '../lib/DialogosContext'
import SeccionPrivacidad from '../components/SeccionPrivacidad'

const f = (aceptado) => ({ aceptado, version: '1.1', fecha_co: '2026-10-03T09:00:00' })

function montar(onEliminarCuenta = vi.fn(), eliminando = false) {
  api.consentimientos.mockResolvedValue({
    finalidades: { tratamiento_basico: f(true), lectura_correo: f(false), ia: f(true), notificaciones: f(false) },
  })
  render(
    <DialogosProvider>
      <MemoryRouter>
        <SeccionPrivacidad onEliminarCuenta={onEliminarCuenta} eliminando={eliminando} />
      </MemoryRouter>
    </DialogosProvider>
  )
  return onEliminarCuenta
}

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset())
})

describe('Descargar mis datos', () => {
  it('explica en palabras simples qué trae y descarga el ZIP completo', async () => {
    api.descargarMisDatos.mockResolvedValue()
    montar()
    expect(await screen.findByText(/Un archivo ZIP con todo lo que CuadraMe guarda de ti/)).toBeInTheDocument()
    await userEvent.click(screen.getByText('Descargar mis datos'))
    await waitFor(() => expect(api.descargarMisDatos).toHaveBeenCalledTimes(1))
  })

  it('si la descarga falla avisa con el mensaje del servidor', async () => {
    api.descargarMisDatos.mockRejectedValue(new Error('Ya descargaste tus datos varias veces.'))
    montar()
    await userEvent.click(await screen.findByText('Descargar mis datos'))
    expect(await screen.findByText('Ya descargaste tus datos varias veces.')).toBeInTheDocument()
  })
})

describe('Borrar mi cuenta y todos mis datos', () => {
  async function abrirHoja() {
    await userEvent.click(await screen.findByText('Borrar mi cuenta y todos mis datos'))
    return screen.findByLabelText(/escribe ELIMINAR/)
  }

  it('abrir la hoja NO borra nada y el botón queda deshabilitado hasta escribir la palabra', async () => {
    const onEliminar = montar()
    const campo = await abrirHoja()
    expect(onEliminar).not.toHaveBeenCalled()
    const borrar = screen.getByRole('button', { name: 'Borrar todo' })
    expect(borrar).toBeDisabled()
    await userEvent.type(campo, 'borrar')
    expect(borrar).toBeDisabled()
    await userEvent.clear(campo)
    await userEvent.type(campo, 'ELIMINAR')
    expect(borrar).toBeEnabled()
  })

  it('con la palabra escrita (aunque sea en minúsculas) llama a eliminar con la confirmación', async () => {
    const onEliminar = montar()
    const campo = await abrirHoja()
    await userEvent.type(campo, 'eliminar')
    await userEvent.click(screen.getByRole('button', { name: 'Borrar todo' }))
    expect(onEliminar).toHaveBeenCalledWith('ELIMINAR')
  })

  it('dice con claridad qué se borra, que incluye Gmail, y que no se puede deshacer', async () => {
    montar()
    await abrirHoja()
    expect(screen.getByText(/para siempre/)).toBeInTheDocument()
    expect(screen.getByText(/le quitamos el permiso a CuadraMe/)).toBeInTheDocument()
    expect(screen.getByText(/No se puede deshacer/)).toBeInTheDocument()
  })

  it('ofrece descargar una copia antes de borrar', async () => {
    api.descargarMisDatos.mockResolvedValue()
    montar()
    await abrirHoja()
    await userEvent.click(screen.getByRole('button', { name: /Primero quiero descargar una copia/ }))
    await waitFor(() => expect(api.descargarMisDatos).toHaveBeenCalled())
  })

  it('Cancelar cierra la hoja sin borrar', async () => {
    const onEliminar = montar()
    await abrirHoja()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.queryByLabelText(/escribe ELIMINAR/)).toBeNull())
    expect(onEliminar).not.toHaveBeenCalled()
  })
})
