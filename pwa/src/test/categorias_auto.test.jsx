import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const CATS = [
  { id: 'k1', nombre: 'Comida', icono: '🍔', orden: 0, activa: true, es_base: true, tipo: 'ambos', color: null, movimientos: 5 },
  { id: 'k2', nombre: 'Ocio', icono: '🎬', orden: 1, activa: true, es_base: true, tipo: 'ambos', color: '#6a5acd', movimientos: 2 },
  { id: 'k3', nombre: 'Mascotas', icono: '🐶', orden: 2, activa: false, es_base: false, tipo: 'gasto', color: null, movimientos: 3 },
  { id: 'k4', nombre: 'Viajes', icono: '✈️', orden: 3, activa: false, es_base: false, tipo: 'gasto', color: null, movimientos: 0 },
]
const MOVS = [
  { id: 'm1', cuenta_id: 'c1', fecha: '2026-10-02T12:00:00', descripcion: 'Compra en JUAN VALDEZ SKANDIA con tarjeta débito', categoria: 'Comida', tipo: 'expense', monto: 12000, fuente: 'conciliacion_extracto', notas: '', cat_origen: 'comercio', cat_confirmada: false },
  { id: 'm2', cuenta_id: 'c1', fecha: '2026-10-01T12:00:00', descripcion: 'Pago arriendo', categoria: 'Hogar', tipo: 'expense', monto: 900000, fuente: 'manual', notas: '', cat_origen: null, cat_confirmada: true },
]

const api = vi.hoisted(() => ({}))
const recargar = vi.hoisted(() => vi.fn())
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({
    cuentas: [{ id: 'c1', nombre: 'Principal', saldo: 1, moneda: 'COP', tipo: 'ahorro' }],
    cargando: false, error: '', recargar: vi.fn().mockResolvedValue(),
  }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({
    categorias: CATS, activas: CATS.filter((c) => c.activa), nombres: ['Comida', 'Ocio'],
    cargando: false, recargar, iconoDe: (n) => ({ Comida: '🍔', Ocio: '🎬' })[n] || '💳', colorDe: () => null,
  }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import Categorias from '../screens/Categorias'
import Movimientos from '../screens/Movimientos'
import SelectorEmoji from '../components/SelectorEmoji'
import { AvisoCategorizados, HojaCambiarCategoria } from '../components/CategorizacionAuto'
import { patronDeComercio } from '../lib/comercio'
import { buscarEmojis, esEmoji } from '../lib/emojis'

function montar(ui, ruta = '/') {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[ruta]}>{ui}</MemoryRouter>
    </DialogosProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    movimientos: vi.fn().mockResolvedValue(MOVS),
    conteoPorRevisar: vi.fn().mockResolvedValue({ auto: 1, otros: 0, total: 1 }),
    confirmarCategorias: vi.fn().mockResolvedValue({ ok: true, confirmados: 1 }),
    recategorizarComercio: vi.fn().mockResolvedValue({ ok: true, actualizados: 3, patron: 'JUAN VALDEZ SKANDIA' }),
    editarCategoria: vi.fn().mockResolvedValue({}),
    crearCategoria: vi.fn().mockResolvedValue({}),
    eliminarCategoria: vi.fn(),
    reordenarCategorias: vi.fn().mockResolvedValue({ ok: true }),
  })
})

describe('Categorías: nada queda inaccesible', () => {
  it('muestra el contador activas/ocultas y la sección de ocultas', () => {
    montar(<Categorias />)
    expect(screen.getByTestId('contador-categorias')).toHaveTextContent('2 activas · 2 ocultas')
    const ocultas = screen.getByRole('region', { name: 'Categorías ocultas' })
    expect(within(ocultas).getByText('Mascotas')).toBeInTheDocument()
    expect(within(ocultas).getByText('Viajes')).toBeInTheDocument()
  })

  it('el interruptor "Mostrar ocultas" las esconde y las vuelve a mostrar', async () => {
    montar(<Categorias />)
    const sw = screen.getByRole('switch', { name: 'Mostrar ocultas' })
    expect(sw).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(sw)
    expect(screen.queryByRole('region', { name: 'Categorías ocultas' })).not.toBeInTheDocument()
    await userEvent.click(sw)
    expect(screen.getByRole('region', { name: 'Categorías ocultas' })).toBeInTheDocument()
  })

  it('reactiva una categoría oculta con un toque', async () => {
    montar(<Categorias />)
    await userEvent.click(screen.getByRole('button', { name: 'Reactivar Mascotas' }))
    expect(api.editarCategoria).toHaveBeenCalledWith('k3', { activa: true })
    expect(recargar).toHaveBeenCalled()
  })

  it('reordena con las flechas', async () => {
    montar(<Categorias />)
    await userEvent.click(screen.getByRole('button', { name: 'Subir Ocio' }))
    expect(api.reordenarCategorias).toHaveBeenCalledWith(['k2', 'k1'])
  })

  it('al eliminar una categoría en uso ofrece mover sus movimientos', async () => {
    const err = Object.assign(new Error('en uso'), { status: 409, detalle: { movimientos: 3 } })
    api.eliminarCategoria.mockRejectedValueOnce(err).mockResolvedValueOnce({ ok: true, movidos: 3 })
    // Mascotas está oculta; se edita desde la sección de ocultas.
    montar(<Categorias />)
    await userEvent.click(screen.getByRole('button', { name: 'Editar Mascotas' }))
    await userEvent.click(screen.getByRole('button', { name: /Eliminar categoría/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Eliminar' }))
    expect(await screen.findByText('Esta categoría está en uso')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Pasar los movimientos a'), 'Ocio')
    await userEvent.click(screen.getByRole('button', { name: 'Mover y eliminar' }))
    await waitFor(() => expect(api.eliminarCategoria).toHaveBeenLastCalledWith('k3', 'Ocio'))
  })
})

describe('Emoji libre', () => {
  it('acepta cualquier emoji escrito con el teclado y rechaza texto', async () => {
    const onChange = vi.fn()
    render(<SelectorEmoji valor="🏷️" onChange={onChange} />)
    const campo = screen.getByLabelText('Escribir un emoji con el teclado')
    fireEvent.change(campo, { target: { value: '🦄' } })
    expect(onChange).toHaveBeenLastCalledWith('🦄')
    onChange.mockClear()
    fireEvent.change(campo, { target: { value: 'a' } })
    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByText(/Solo se aceptan emojis/)).toBeInTheDocument()
  })

  it('busca por nombre y elige de la cuadrícula', async () => {
    const onChange = vi.fn()
    render(<SelectorEmoji valor="🏷️" onChange={onChange} />)
    await userEvent.type(screen.getByLabelText('Buscar emoji'), 'perro')
    await userEvent.click(screen.getByRole('button', { name: 'Elegir 🐶' }))
    expect(onChange).toHaveBeenCalledWith('🐶')
  })

  it('valida emojis en el cliente', () => {
    expect(esEmoji('🦄')).toBe(true)
    expect(esEmoji('👨‍👩‍👧')).toBe(true)
    expect(esEmoji('abc')).toBe(false)
    expect(esEmoji('')).toBe(false)
    expect(buscarEmojis('cafe')).toContain('☕')
  })
})

describe('Auto-categorización visible', () => {
  it('extrae el comercio de una descripción bancaria', () => {
    expect(patronDeComercio('Compra en JUAN VALDEZ SKANDIA con tarjeta débito')).toBe('JUAN VALDEZ SKANDIA')
    expect(patronDeComercio('Rappi')).toBe('Rappi')
  })

  it('muestra la insignia Auto con la razón solo en lo categorizado por la app', async () => {
    montar(<Movimientos />)
    expect(await screen.findByText(/Auto · por comercio conocido/)).toBeInTheDocument()
    expect(screen.getAllByText(/^Auto/)).toHaveLength(1)
  })

  it('el filtro "Por revisar" pide solo los pendientes y permite confirmar con un toque', async () => {
    montar(<Movimientos />)
    const chip = await screen.findByRole('button', { name: /Por revisar \(1\)/ })
    await userEvent.click(chip)
    await waitFor(() => expect(api.movimientos).toHaveBeenLastCalledWith(200, 0, { porRevisar: true }))
    await userEvent.click(await screen.findByRole('button', { name: /Confirmar categoría de Compra en JUAN VALDEZ/ }))
    expect(api.confirmarCategorias).toHaveBeenCalledWith(['m1'])
  })

  it('abre directo en "Por revisar" desde el resumen de importación', async () => {
    montar(<Movimientos />, '/movimientos?revisar=1')
    await waitFor(() => expect(api.movimientos).toHaveBeenCalledWith(200, 0, { porRevisar: true }))
  })

  it('cambiar la categoría con "aplicar a todos" crea la regla del comercio', async () => {
    const onHecho = vi.fn()
    render(
      <MemoryRouter>
        <HojaCambiarCategoria movimiento={MOVS[0]} onClose={vi.fn()} onHecho={onHecho} />
      </MemoryRouter>
    )
    expect(screen.getByLabelText('Comercio de la regla')).toHaveValue('JUAN VALDEZ SKANDIA')
    await userEvent.click(screen.getByRole('button', { name: /Ocio/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() =>
      expect(api.recategorizarComercio).toHaveBeenCalledWith('m1', {
        categoria: 'Ocio', aplicar_a_todos: true, patron: 'JUAN VALDEZ SKANDIA',
      })
    )
    expect(onHecho).toHaveBeenCalled()
  })

  it('el resumen tras importar lleva a la vista Por revisar', () => {
    render(
      <MemoryRouter>
        <AvisoCategorizados n={12} />
      </MemoryRouter>
    )
    const enlace = screen.getByRole('link')
    expect(enlace).toHaveTextContent('Categoricé 12 movimientos')
    expect(enlace).toHaveAttribute('href', '/movimientos?revisar=1')
  })
})
