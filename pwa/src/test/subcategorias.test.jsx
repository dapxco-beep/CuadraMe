import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const subs = [
  { id: 's1', categoria: 'Transporte', nombre: 'Gasolina', movimientos: 2 },
  { id: 's2', categoria: 'Transporte', nombre: 'Uber', movimientos: 0 },
]
const recargar = vi.fn(async () => {})
const confirmar = vi.fn(async () => true)
const avisar = vi.fn()

vi.mock('../lib/api', () => ({
  api: {
    crearSubcategoria: vi.fn(async (categoria, nombre) => ({ id: 'nueva', categoria, nombre, movimientos: 0 })),
    editarSubcategoria: vi.fn(async () => ({})),
    eliminarSubcategoria: vi.fn(async () => ({ ok: true })),
    desgloseSubcategorias: vi.fn(async () => ({
      categoria: 'Transporte',
      total: 150000,
      tiene_subcategorias: true,
      subcategorias: [
        { subcategoria: 'Gasolina', total: 100000, cantidad: 2, porcentaje: 67 },
        { subcategoria: null, total: 50000, cantidad: 1, porcentaje: 33 },
      ],
    })),
    similaresConteo: vi.fn(async () => ({ conteo: 0 })),
  },
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({
    categorias: [
      { id: 'c1', nombre: 'Transporte', icono: '🚗', orden: 0, activa: true, es_base: true, es_sistema: false, tipo: 'ambos', movimientos: 3 },
      { id: 'c2', nombre: 'Comida', icono: '🍔', orden: 1, activa: true, es_base: true, es_sistema: false, tipo: 'ambos', movimientos: 1 },
    ],
    nombres: ['Transporte', 'Comida'],
    iconoDe: () => '🏷️',
    cargando: false,
    recargar,
    subcategorias: subs,
    subsDe: (c) => subs.filter((s) => s.categoria === c),
  }),
}))
vi.mock('../lib/DialogosContext', () => ({ useDialogos: () => ({ confirmar, avisar }) }))
vi.mock('../lib/BloqueoContext', () => ({ useBloqueo: () => ({ fmt: (v) => `$${v}` }) }))

import { api } from '../lib/api'
import SelectorCategoria from '../components/SelectorCategoria'
import Categorias from '../screens/Categorias'
import DesgloseSubcategorias from '../components/DesgloseSubcategorias'

beforeEach(() => vi.clearAllMocks())

describe('Selector de categoría con subcategorías', () => {
  it('una categoría con subcategorías abre el paso 2 y se puede elegir una', async () => {
    const onElegir = vi.fn()
    render(<SelectorCategoria onElegir={onElegir} onCerrar={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /Transporte/ }))
    expect(onElegir).not.toHaveBeenCalled()
    const paso = screen.getByTestId('paso-subcategoria')
    await userEvent.click(within(paso).getByRole('button', { name: 'Gasolina' }))
    expect(onElegir).toHaveBeenCalledWith('Transporte', expect.objectContaining({ subcategoria: 'Gasolina' }))
  })

  it('«Solo Transporte» salta la subcategoría (es opcional)', async () => {
    const onElegir = vi.fn()
    render(<SelectorCategoria onElegir={onElegir} onCerrar={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /Transporte/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Solo Transporte' }))
    expect(onElegir).toHaveBeenCalledTimes(1)
    expect(onElegir.mock.calls[0][0]).toBe('Transporte')
    expect(onElegir.mock.calls[0][1].subcategoria).toBeUndefined()
  })

  it('una categoría sin subcategorías guarda de una, sin paso extra', async () => {
    const onElegir = vi.fn()
    render(<SelectorCategoria onElegir={onElegir} onCerrar={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /Comida/ }))
    expect(onElegir).toHaveBeenCalledWith('Comida', expect.not.objectContaining({ subcategoria: expect.anything() }))
    expect(screen.queryByTestId('paso-subcategoria')).not.toBeInTheDocument()
  })

  it('«+ Nueva subcategoría» crea y asigna en un toque', async () => {
    const onElegir = vi.fn()
    render(<SelectorCategoria onElegir={onElegir} onCerrar={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /Transporte/ }))
    await userEvent.click(screen.getByRole('button', { name: '+ Nueva subcategoría' }))
    await userEvent.type(screen.getByLabelText('Nombre de la subcategoría'), 'Peajes')
    await userEvent.click(screen.getByRole('button', { name: 'Crear y poner' }))
    await waitFor(() => expect(api.crearSubcategoria).toHaveBeenCalledWith('Transporte', 'Peajes'))
    await waitFor(() =>
      expect(onElegir).toHaveBeenCalledWith('Transporte', expect.objectContaining({ subcategoria: 'Peajes' }))
    )
  })

  it('«Con subcategoría» permite crear la primera en una categoría que no tiene', async () => {
    const onElegir = vi.fn()
    render(<SelectorCategoria onElegir={onElegir} onCerrar={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: 'Con subcategoría' }))
    await userEvent.click(screen.getByRole('button', { name: /Comida/ }))
    await userEvent.type(screen.getByLabelText('Nombre de la subcategoría'), 'Domicilios')
    await userEvent.click(screen.getByRole('button', { name: 'Crear y poner' }))
    await waitFor(() => expect(api.crearSubcategoria).toHaveBeenCalledWith('Comida', 'Domicilios'))
    await waitFor(() =>
      expect(onElegir).toHaveBeenCalledWith('Comida', expect.objectContaining({ subcategoria: 'Domicilios' }))
    )
  })

  it('pantallas sin soporte (conSubcategorias=false) siguen en un solo paso', async () => {
    const onElegir = vi.fn()
    render(<SelectorCategoria conSubcategorias={false} onElegir={onElegir} onCerrar={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /Transporte/ }))
    expect(onElegir).toHaveBeenCalledTimes(1)
  })
})

describe('Pantalla de Categorías con subcategorías', () => {
  it('se abre una categoría, se agrega una subcategoría y se borra otra', async () => {
    render(<MemoryRouter><Categorias /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: 'Subcategorías de Transporte' }))
    const panel = screen.getByTestId('subcategorias-Transporte')
    expect(within(panel).getByText(/Gasolina/)).toBeInTheDocument()
    expect(within(panel).getByText(/Uber/)).toBeInTheDocument()

    await userEvent.click(within(panel).getByRole('button', { name: /Agregar subcategoría/ }))
    await userEvent.type(within(panel).getByLabelText('Nombre de la subcategoría'), 'Peajes')
    await userEvent.click(within(panel).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(api.crearSubcategoria).toHaveBeenCalledWith('Transporte', 'Peajes'))
    expect(recargar).toHaveBeenCalled()

    await userEvent.click(within(panel).getByRole('button', { name: 'Borrar subcategoría Gasolina' }))
    await waitFor(() => expect(api.eliminarSubcategoria).toHaveBeenCalledWith('s1'))
    // avisa que los movimientos se quedan en la categoría
    expect(confirmar.mock.calls[0][0]).toMatch(/Siguen en Transporte/)
  })

  it('renombra una subcategoría', async () => {
    render(<MemoryRouter><Categorias /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: 'Subcategorías de Transporte' }))
    await userEvent.click(screen.getByRole('button', { name: 'Editar subcategoría Uber' }))
    const campo = screen.getByLabelText('Nuevo nombre de Uber')
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Taxi')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar nombre' }))
    await waitFor(() => expect(api.editarSubcategoria).toHaveBeenCalledWith('s2', 'Taxi'))
  })
})

describe('Desglose por subcategoría', () => {
  it('muestra cada subcategoría y «Sin subcategoría»', async () => {
    render(<DesgloseSubcategorias categoria="Transporte" />)
    await userEvent.click(screen.getByRole('button', { name: /Ver por subcategoría/ }))
    await waitFor(() => expect(api.desgloseSubcategorias).toHaveBeenCalledWith('Transporte', { periodo: 'este_mes' }))
    const lista = await screen.findByRole('list', { name: 'Subcategorías de Transporte' })
    expect(within(lista).getByText('Gasolina')).toBeInTheDocument()
    expect(within(lista).getByText('Sin subcategoría')).toBeInTheDocument()
    expect(within(lista).getByText(/67 %/)).toBeInTheDocument()
  })

  it('no aparece si la categoría no tiene subcategorías', () => {
    render(<DesgloseSubcategorias categoria="Comida" />)
    expect(screen.queryByRole('button', { name: /Ver por subcategoría/ })).not.toBeInTheDocument()
  })
})
