import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../lib/api', () => ({ api: { crearCuenta: vi.fn(async (d) => ({ id: 'x', ...d })) } }))
vi.mock('../lib/BloqueoContext', () => ({
  useBloqueo: () => ({ fmt: (v) => `$${v}` }),
}))

import { api } from '../lib/api'
import CrearCuenta from '../screens/CrearCuenta'
import MazoCuentas from '../components/MazoCuentas'

const cuentas = [
  { id: 'a', nombre: 'Nu Colombia', saldo: 49990, moneda: 'COP' },
  { id: 'b', nombre: 'Bancolombia Ahorros', saldo: 100000, moneda: 'COP' },
  { id: 'c', nombre: 'Efectivo', saldo: 5000, moneda: 'COP' },
]

describe('Primer registro con selección', () => {
  it('elige país, tipo y banco con toques y crea la cuenta sin escribir', async () => {
    render(<MemoryRouter><CrearCuenta onCreada={vi.fn()} /></MemoryRouter>)
    await userEvent.click(screen.getByText(/Empezar/))
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar país' }))
    await userEvent.click(screen.getByRole('button', { name: /Estados Unidos/ }))
    expect(screen.getByRole('button', { name: 'USD' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar país' }))
    await userEvent.click(screen.getByRole('button', { name: /Colombia/ }))
    expect(screen.getByRole('button', { name: 'COP' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: /Tarjeta de crédito/ }))
    await userEvent.click(screen.getByRole('button', { name: /Nequi/ }))
    expect(screen.getByLabelText('Nombre de la cuenta')).toHaveValue('Nequi Crédito')
    await userEvent.click(screen.getByText('Crear mi cuenta'))
    await waitFor(() =>
      expect(api.crearCuenta).toHaveBeenCalledWith(
        expect.objectContaining({ nombre: 'Nequi Crédito', tipo: 'credito', moneda: 'COP' })
      )
    )
  })

  it('efectivo no pide banco y se llama Efectivo', async () => {
    render(<MemoryRouter><CrearCuenta onCreada={vi.fn()} /></MemoryRouter>)
    await userEvent.click(screen.getByText(/Empezar/))
    await userEvent.click(screen.getByRole('button', { name: /Efectivo/ }))
    expect(screen.getByLabelText('Nombre de la cuenta')).toHaveValue('Efectivo')
    expect(screen.queryByText(/Cuál es tu banco/)).not.toBeInTheDocument()
  })

  it('"Ver todas" permite buscar un banco fuera de los populares', async () => {
    render(<MemoryRouter><CrearCuenta onCreada={vi.fn()} /></MemoryRouter>)
    await userEvent.click(screen.getByText(/Empezar/))
    await userEvent.click(screen.getByText('Ver todas'))
    await userEvent.type(screen.getByLabelText('Buscar banco'), 'falabella')
    await userEvent.click(screen.getByRole('button', { name: /Banco Falabella/ }))
    expect(screen.getByLabelText('Nombre de la cuenta')).toHaveValue('Banco Falabella')
  })
})

describe('Mazo de cuentas', () => {
  it('muestra la primera cuenta al frente y las demás apiladas', () => {
    render(<MemoryRouter><MazoCuentas cuentas={cuentas} /></MemoryRouter>)
    expect(screen.getByText('Nu Colombia')).toBeInTheDocument()
    expect(screen.getByText('Bancolombia Ahorros')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /Tus cuentas, 3/ })).toBeInTheDocument()
  })

  it('los puntos permiten traer una cuenta al frente sin arrastrar', async () => {
    render(<MemoryRouter><MazoCuentas cuentas={cuentas} /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: 'Ver Bancolombia Ahorros' }))
    expect(screen.getByRole('button', { name: 'Ver Bancolombia Ahorros' })).toHaveAttribute('aria-current', 'true')
    const grupo = screen.getByRole('group', { name: /Tus cuentas/ })
    const textos = Array.from(grupo.querySelectorAll('span.truncate')).map((n) => n.textContent)
    expect(textos[0]).toBe('Bancolombia Ahorros')
  })

  it('sin cuentas no pinta nada', () => {
    const { container } = render(<MemoryRouter><MazoCuentas cuentas={[]} /></MemoryRouter>)
    expect(container).toBeEmptyDOMElement()
  })
})
