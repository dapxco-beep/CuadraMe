// Agregar: pasar plata sin internet da un mensaje claro (y conserva el monto); «Cancelar» vuelve.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const CUENTAS = [
  { id: 'c1', nombre: 'Bancolombia', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
  { id: 'c2', nombre: 'Nequi', saldo: 50000, moneda: 'COP', tipo: 'ahorro', icono: '💜' },
]

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ categorias: [], nombres: ['Mercado', 'Otros'], cargando: false, recargar: vi.fn(), iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Agregar from '../screens/Agregar'

function montar() {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter initialEntries={['/agregar?tipo=transfer']}>
          <Agregar />
        </MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.keys(api).forEach((k) => delete api[k])
  api.movimientos = vi.fn().mockResolvedValue([])
})

describe('Agregar sin conexión', () => {
  it('una transferencia sin internet explica por qué y no borra el monto', async () => {
    api.crearTransferencia = vi.fn().mockRejectedValue(Object.assign(new Error('Failed to fetch'), { sinConexion: true }))
    montar()
    await userEvent.type(screen.getByPlaceholderText('0'), '20000')
    await userEvent.click(screen.getByRole('button', { name: /Pasar la plata/ }))
    expect(await screen.findByText('Pasar plata necesita internet; inténtalo cuando tengas señal.')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('0')).toHaveValue('20.000')
  })

  it('tiene un «Cancelar» debajo de Guardar', () => {
    montar()
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeInTheDocument()
  })
})
