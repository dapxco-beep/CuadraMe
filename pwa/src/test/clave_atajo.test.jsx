// Clave del Atajo guardada como hash: se muestra completa solo al crearla; antes de que exista
// la columna en la base (clave en claro) todo sigue funcionando igual.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  apiKey: vi.fn(),
  regenerarApiKey: vi.fn(),
  pagoDePrueba: vi.fn(),
  registroRapidoDePrueba: vi.fn(),
  movimientosPorConfirmar: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))

import { DialogosProvider } from '../lib/DialogosContext'
import ConectarDispositivo from '../screens/ConectarDispositivo'

const montar = () =>
  render(
    <DialogosProvider>
      <MemoryRouter>
        <ConectarDispositivo />
      </MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
})

describe('Clave del Atajo', () => {
  it('clave ya guardada: muestra solo el principio y ofrece crear una nueva con advertencia simple', async () => {
    api.apiKey.mockResolvedValue({ api_key: null, tiene_clave: true, prefijo: 'cdm_ab12…' })
    api.regenerarApiKey.mockResolvedValue({ api_key: 'cdm_ab12NUEVA', tiene_clave: true, nueva: true })
    montar()
    expect(await screen.findByText(/cdm_ab12…/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Copiar clave' })).toBeNull()

    await userEvent.click(screen.getAllByRole('button', { name: 'Crear una clave nueva' })[0])
    expect(api.regenerarApiKey).not.toHaveBeenCalled() // pide confirmar antes
    expect(await screen.findByText(/dejará de funcionar hasta que pegues la clave nueva/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Sí, crear clave nueva/ }))

    expect(await screen.findByText('cdm_ab12NUEVA')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(/Cópiala ahora/)
    expect(screen.getByRole('alert')).toHaveTextContent(/no se vuelve a mostrar/)
    expect(screen.getByRole('button', { name: 'Copiar clave' })).toBeInTheDocument()
  })

  it('probar la conexión funciona sin la clave guardada (usa la sesión)', async () => {
    api.apiKey.mockResolvedValue({ api_key: null, tiene_clave: true, prefijo: 'cdm_ab12…' })
    api.pagoDePrueba.mockResolvedValue({ id: 'p1', mensaje: 'ok' })
    api.movimientosPorConfirmar.mockResolvedValue([{ id: 'p1' }])
    montar()
    await screen.findByText(/cdm_ab12…/)
    const boton = screen.getByRole('button', { name: /Enviar un pago de prueba/ })
    expect(boton).not.toBeDisabled()
    await userEvent.click(boton)
    expect(await screen.findByText('¡Funciona!')).toBeInTheDocument()
    expect(api.pagoDePrueba).toHaveBeenCalledWith(null)
  })

  it('clave antigua en claro (columnas aún sin crear): se ve y se copia como siempre, sin aviso de "no se vuelve a mostrar"', async () => {
    api.apiKey.mockResolvedValue({ api_key: 'cdm_vieja_en_claro' })
    montar()
    expect(await screen.findByText('cdm_vieja_en_claro')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copiar clave' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('usuario sin clave: la primera vez se muestra con el aviso de copiarla ahora', async () => {
    api.apiKey.mockResolvedValue({ api_key: 'cdm_primera', tiene_clave: true, nueva: true })
    montar()
    expect(await screen.findByText('cdm_primera')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/Cópiala ahora/))
  })
})
