import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'
import { useState } from 'react'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'ahorros', nombre: 'Nu Colombia' }, { id: 'credito', nombre: 'Nu Crédito' }] }),
}))

import SobrantesExtracto from '../components/SobrantesExtracto'

const LISTA = [
  { id: 'm1', fecha: '2026-10-18', descripcion: 'Dollarcity Floresta', monto: 18000 },
  { id: 'm2', fecha: '2026-10-23', descripcion: 'Estacion Terpel', monto: 39979 },
  { id: 'm3', fecha: '2026-10-28', descripcion: 'Novaventa', monto: 5300 },
  { id: 'm4', fecha: '2026-10-28', descripcion: 'Santiago Quintero', monto: 47000 },
]

// El padre guarda la lista, como hace SubidaMultiple con «parchar».
function Caja({ inicial = LISTA }) {
  const [lista, setLista] = useState(inicial)
  return <MemoryRouter><SobrantesExtracto historialId="h1" cuentaId="ahorros" sobrantes={lista} onCambio={setLista} /></MemoryRouter>
}

beforeEach(() => {
  vi.clearAllMocks()
  api.editarMovimiento = vi.fn().mockResolvedValue({})
  api.resolverSobrante = vi.fn().mockImplementation(async (_h, _m, accion) => ({ ok: true, resuelto: accion === 'borrar' ? 'borrado' : 'dejado' }))
})

describe('Movimientos tuyos que el extracto no trae', () => {
  it('lista los 4, explica qué hacer y cuenta los pendientes', () => {
    render(<Caja />)
    expect(screen.getByText('4 movimientos tuyos no están en el extracto')).toBeInTheDocument()
    expect(screen.getAllByTestId('sobrante')).toHaveLength(4)
    expect(screen.getByText(/si es real/)).toBeInTheDocument()
  })

  it('«Dejar» guarda la decisión en el servidor y baja el contador', async () => {
    const user = userEvent.setup()
    render(<Caja />)
    const fila = screen.getAllByTestId('sobrante')[0]
    await user.click(within(fila).getByRole('button', { name: 'Dejar' }))
    await waitFor(() => expect(api.resolverSobrante).toHaveBeenCalledWith('h1', 'm1', 'dejar', 'no_va'))
    expect(await screen.findByText('3 movimientos tuyos no están en el extracto')).toBeInTheDocument()
    expect(within(fila).getByText('Se queda como está')).toBeInTheDocument()
    expect(within(fila).queryByRole('button', { name: 'Dejar' })).toBeNull()
  })

  it('«Borrar» borra ese movimiento y lo marca como borrado', async () => {
    const user = userEvent.setup()
    render(<Caja />)
    const fila = screen.getAllByTestId('sobrante')[1]
    await user.click(within(fila).getByRole('button', { name: 'Borrar' }))
    await waitFor(() => expect(api.resolverSobrante).toHaveBeenCalledWith('h1', 'm2', 'borrar', 'no_va'))
    expect(await within(fila).findByText('Borrado')).toBeInTheDocument()
  })

  it('«Dejar todos» resuelve los pendientes de una vez y el aviso queda en «Revisaste…»', async () => {
    const user = userEvent.setup()
    render(<Caja />)
    await user.click(screen.getByRole('button', { name: 'Dejar todos' }))
    await waitFor(() => expect(api.resolverSobrante).toHaveBeenCalledTimes(4))
    expect(await screen.findByText('Revisaste los movimientos que el extracto no trae')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Dejar todos' })).toBeNull()
  })

  it('«Otra cuenta» mueve el movimiento a la cuenta correcta (la actual no se ofrece) y lo marca resuelto', async () => {
    const user = userEvent.setup()
    render(<Caja />)
    const fila = screen.getAllByTestId('sobrante')[1]
    await user.click(within(fila).getByRole('button', { name: 'Otra cuenta' }))
    const lista = within(fila).getByRole('combobox')
    expect(within(lista).queryByRole('option', { name: 'Nu Colombia' })).toBeNull()
    await user.selectOptions(lista, 'credito')
    await user.click(within(fila).getByRole('button', { name: 'Mover' }))
    await waitFor(() => expect(api.editarMovimiento).toHaveBeenCalledWith('m2', { cuenta_id: 'credito' }))
    expect(await within(fila).findByText('Movido a Nu Crédito')).toBeInTheDocument()
    expect(await screen.findByText('3 movimientos tuyos no están en el extracto')).toBeInTheDocument()
  })

  it('si falla el servidor no marca nada como resuelto', async () => {
    const user = userEvent.setup()
    api.resolverSobrante = vi.fn().mockRejectedValue(new Error('sin red'))
    render(<Caja />)
    await user.click(within(screen.getAllByTestId('sobrante')[0]).getByRole('button', { name: 'Dejar' }))
    await waitFor(() => expect(api.resolverSobrante).toHaveBeenCalled())
    expect(screen.getByText('4 movimientos tuyos no están en el extracto')).toBeInTheDocument()
  })

  it('sin movimientos no pinta nada', () => {
    const { container } = render(<Caja inicial={[]} />)
    expect(container.querySelector('[data-testid="sobrantes-extracto"]')).toBeNull()
  })
})

describe('Repetido que la app unió sola', () => {
  it('avisa que lo unió y «Deshacer» lo devuelve', async () => {
    render(<Caja inicial={[{ id: 'm9', fecha: '2026-10-14', descripcion: 'Juliana', monto: 1060000, resuelto: 'unido' }]} />)
    expect(screen.getByText('Unimos un movimiento repetido')).toBeInTheDocument()
    expect(screen.getByText(/lo unimos con el del banco/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }))
    await waitFor(() => expect(api.resolverSobrante).toHaveBeenCalledWith('h1', 'm9', 'restaurar'))
    await waitFor(() => expect(screen.getByText('Se queda como está')).toBeInTheDocument())
  })
})
