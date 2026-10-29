import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import { DialogosProvider } from '../lib/DialogosContext'
import CompartirEnParche from '../components/CompartirEnParche'
import { compartirMovimientoEnParche } from '../lib/hogares'

const MOV = { id: 'm1', tipo: 'expense', descripcion: 'Cena', monto: 90000, categoria: 'Comida' }
const PARCHE = { id: 'h1', nombre: 'Apartamento', miembros: [{ id: 'ma', activo: true }, { id: 'mb', activo: true }, { id: 'mc', activo: false }] }

const montar = (movimiento = MOV) =>
  render(
    <DialogosProvider>
      <MemoryRouter>
        <CompartirEnParche movimiento={movimiento} />
      </MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    hogares: vi.fn().mockResolvedValue([{ id: 'h1', nombre: 'Apartamento' }, { id: 'h2', nombre: 'Viaje' }]),
    parchesDeMovimiento: vi.fn().mockResolvedValue([]),
    hogar: vi.fn().mockResolvedValue(PARCHE),
    crearGastoHogar: vi.fn().mockResolvedValue({ id: 'g1' }),
  })
})

describe('compartir un gasto ya registrado en un parche', () => {
  it('la lib divide entre los miembros activos, con el movimiento de origen y sin inventar un monto', async () => {
    const r = await compartirMovimientoEnParche('h1', MOV)
    expect(r).toEqual({ parche: 'Apartamento', personas: 2 })
    expect(api.crearGastoHogar).toHaveBeenCalledWith('h1', {
      descripcion: 'Cena', total: 90000, modo: 'iguales', participantes: [{ id: 'ma' }, { id: 'mb' }], movimiento_id: 'm1', categoria: 'Comida',
    })
  })

  it('eliges el parche y compartes con un toque', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('radio', { name: 'Apartamento' }))
    await user.click(screen.getByRole('button', { name: 'Compartir' }))
    await waitFor(() => expect(api.crearGastoHogar).toHaveBeenCalled())
    expect(api.crearGastoHogar.mock.calls[0][1].movimiento_id).toBe('m1')
  })

  it('con un solo parche ya viene elegido', async () => {
    api.hogares.mockResolvedValue([{ id: 'h1', nombre: 'Apartamento' }])
    montar()
    expect(await screen.findByRole('radio', { name: 'Apartamento' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('button', { name: 'Compartir' })).toBeEnabled()
  })

  it('si ya está compartido lo dice y lleva al parche, sin ofrecer compartir otra vez', async () => {
    api.parchesDeMovimiento.mockResolvedValue([{ hogar_id: 'h1', nombre: 'Apartamento', gasto_id: 'g1', mi_parte: 45000 }])
    montar()
    expect(await screen.findByText('Compartido en Apartamento')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Ver el parche' })).toHaveAttribute('href', '/hogares/h1')
    expect(screen.queryByRole('button', { name: 'Compartir' })).toBeNull()
  })

  it('sin parches invita a crear uno', async () => {
    api.hogares.mockResolvedValue([])
    montar()
    expect(await screen.findByRole('link', { name: 'Crear un parche' })).toHaveAttribute('href', '/hogares')
  })

  it('los ingresos y las transferencias no se comparten (no sale nada)', async () => {
    const { container } = montar({ ...MOV, tipo: 'income' })
    await waitFor(() => expect(api.hogares).toHaveBeenCalled())
    expect(container.querySelector('section')).toBeNull()
  })

  it('un error del servidor se dice con palabras', async () => {
    const user = userEvent.setup()
    api.crearGastoHogar.mockRejectedValue(Object.assign(new Error('x'), { status: 409 }))
    montar()
    await user.click(await screen.findByRole('radio', { name: 'Viaje' }))
    await user.click(screen.getByRole('button', { name: 'Compartir' }))
    expect(await screen.findByText('Este gasto ya está compartido en un parche.')).toBeTruthy()
  })
})
