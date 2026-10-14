import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Ocio'], iconoDe: () => '💳', recargar: vi.fn() }),
}))

import SugerenciasReglas from '../components/SugerenciasReglas'
import ReglasCategoria from '../screens/ReglasCategoria'

const SUG = [
  { huella: 'kopi zebra', categoria: 'Comida', conteo: 4, monto_total: 40000, ejemplo: 'KOPI ZEBRA' },
  { huella: 'xanadu royal', categoria: 'Ocio', conteo: 3, monto_total: 90000, ejemplo: 'XANADU ROYAL' },
]

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    sugerenciasReglas: vi.fn().mockResolvedValue({ sugerencias: SUG, total: 2 }),
    crearSugerencias: vi.fn().mockResolvedValue({ ok: true, creadas: ['kopi zebra'] }),
    descartarSugerencias: vi.fn().mockResolvedValue({ ok: true }),
    restaurarSugerencias: vi.fn().mockResolvedValue({ ok: true }),
    reglasCategoria: vi.fn().mockResolvedValue([
      { id: 'r1', patron: 'netflix', categoria: 'Ocio', tipo: null, activa: true },
      { id: 'r2', patron: 'uber', categoria: 'Transporte', tipo: null, activa: false },
    ]),
    reglasEnLote: vi.fn().mockResolvedValue({ ok: true, afectadas: 2 }),
  })
})

describe('sugerencias de reglas', () => {
  it('salen sin marcar y no se crea nada hasta elegir', async () => {
    render(<SugerenciasReglas />)
    const a = await screen.findByRole('checkbox', { name: /Crear regla: kopi zebra es Comida/ })
    expect(a).not.toBeChecked()
    expect(screen.getByRole('button', { name: /Crear las seleccionadas/ })).toBeDisabled()
    expect(api.crearSugerencias).not.toHaveBeenCalled()
  })

  it('crea solo las seleccionadas', async () => {
    const user = userEvent.setup()
    render(<SugerenciasReglas />)
    await user.click(await screen.findByRole('checkbox', { name: /kopi zebra/ }))
    await user.click(screen.getByRole('button', { name: /Crear las seleccionadas \(1\)/ }))
    await waitFor(() => expect(api.crearSugerencias).toHaveBeenCalledWith([{ huella: 'kopi zebra', categoria: 'Comida' }]))
  })

  it('descartar no vuelve a sugerir y se puede deshacer', async () => {
    const user = userEvent.setup()
    render(<SugerenciasReglas />)
    await user.click(await screen.findByRole('button', { name: /Descartar la sugerencia de xanadu royal/ }))
    await waitFor(() => expect(api.descartarSugerencias).toHaveBeenCalledWith(['xanadu royal']))
    await user.click(await screen.findByRole('button', { name: /Deshacer/ }))
    await waitFor(() => expect(api.restaurarSugerencias).toHaveBeenCalledWith(['xanadu royal']))
  })
})

describe('reglas en lote', () => {
  it('selecciona varias y las pausa; marca las que están en pausa', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <ReglasCategoria />
      </MemoryRouter>
    )
    expect(await screen.findByText('En pausa')).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: 'Seleccionar la regla netflix' }))
    await user.click(screen.getByRole('checkbox', { name: 'Seleccionar la regla uber' }))
    await user.click(screen.getByRole('button', { name: /Pausar/ }))
    await waitFor(() => expect(api.reglasEnLote).toHaveBeenCalledWith(['r1', 'r2'], 'pausar'))
  })
})
