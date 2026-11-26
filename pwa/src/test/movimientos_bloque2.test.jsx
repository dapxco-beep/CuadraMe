// Movimientos (rediseño bloque 2): vista guardada, tabla en escritorio y estado «sin resultados».
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const DATOS = Array.from({ length: 30 }, (_, i) => ({
  id: `m${i}`, descripcion: `Compra ${i}`, categoria: 'Comida', tipo: 'expense', monto: 1000 + i,
  fecha: new Date('2026-09-20T12:00:00').toISOString(), cuenta_id: 'c1', fuente: 'manual', notas: '', cat_origen: null, cat_confirmada: true,
}))
const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => {
  const valor = { cuentas: [{ id: 'c1', nombre: 'Principal', saldo: 1, moneda: 'COP', tipo: 'ahorro' }], cargando: false, error: '', recargar: () => Promise.resolve() }
  return { useCuentas: () => valor }
})
vi.mock('../lib/CategoriasContext', () => {
  const valor = { categorias: [], activas: [], nombres: ['Comida'], cargando: false, recargar: () => Promise.resolve(), iconoDe: () => '💳', colorDe: () => '#000' }
  return { useCategorias: () => valor }
})

import { DialogosProvider } from '../lib/DialogosContext'
import { vaciarCachesListas } from '../lib/useEstadoLista'
import Movimientos from '../screens/Movimientos'

const matchOriginal = window.matchMedia
beforeEach(() => {
  vaciarCachesListas()
  window.sessionStorage.clear()
  window.localStorage.clear()
  window.matchMedia = (q) => ({ matches: true, media: q, addEventListener() {}, removeEventListener() {} })
  api.movimientos = vi.fn((limite, desplazamiento, filtros) =>
    Promise.resolve(filtros?.q ? [] : DATOS.slice(desplazamiento, desplazamiento + limite)))
  api.conteoPorRevisar = vi.fn().mockResolvedValue({ auto: 0, otros: 0, total: 0 })
})
afterEach(() => { window.matchMedia = matchOriginal })

const montar = (ruta) => render(
  <DialogosProvider><MemoryRouter initialEntries={[ruta]}><Movimientos /></MemoryRouter></DialogosProvider>
)

describe('Movimientos: vista y estados', () => {
  it('?vista=tabla pinta la tabla; la lista, no', async () => {
    montar('/movimientos?vista=tabla')
    expect(await screen.findByRole('table', { name: 'Movimientos en tabla' })).toBeInTheDocument()
  })
  it('la vista elegida antes (lista) se recuerda y gana a la tabla por defecto', async () => {
    window.localStorage.setItem('cuadrame:mov-vista', 'lista')
    montar('/movimientos')
    await screen.findAllByText(/Compra 0/)
    expect(screen.queryByRole('table', { name: 'Movimientos en tabla' })).toBeNull()
  })
  it('una búsqueda sin coincidencias dice que no hay y ofrece quitar los filtros', async () => {
    montar('/movimientos?q=zzzz&vista=lista')
    expect(await screen.findByText('No hay movimientos que coincidan')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Quitar los filtros' })).toBeInTheDocument()
  })
  it('el encabezado del día es un título (h2) para quien navega con lector de pantalla', async () => {
    montar('/movimientos?vista=lista')
    await screen.findAllByText(/Compra 0/)
    expect(document.querySelectorAll('h2').length).toBeGreaterThan(0)
  })
})
