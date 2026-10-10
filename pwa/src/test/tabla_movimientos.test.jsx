// Vista de tabla de Movimientos en escritorio (>= 1024 px): columnas, orden, virtualización y selección.
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const TOTAL = 1500
function generar(n) {
  const base = new Date('2026-09-30T12:00:00')
  return Array.from({ length: n }, (_, i) => {
    const fecha = new Date(base)
    fecha.setDate(base.getDate() - Math.floor(i / 5))
    return {
      id: `m${i}`, descripcion: `Compra ${String(i).padStart(4, '0')}`, categoria: i % 2 ? 'Comida' : 'Ocio',
      tipo: 'expense', monto: 1000 + i, fecha: fecha.toISOString(), cuenta_id: 'c1', fuente: 'manual', notas: '',
      cat_origen: null, cat_confirmada: true,
    }
  })
}
const DATOS = generar(TOTAL)

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => {
  const valor = { cuentas: [{ id: 'c1', nombre: 'Principal', saldo: 1, moneda: 'COP', tipo: 'ahorro' }], cargando: false, error: '', recargar: () => Promise.resolve() }
  return { useCuentas: () => valor }
})
vi.mock('../lib/CategoriasContext', () => {
  const valor = { categorias: [], activas: [], nombres: ['Comida', 'Ocio', 'Otros'], cargando: false, recargar: () => Promise.resolve(), iconoDe: () => '💳', colorDe: () => null }
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
  window.matchMedia = (q) => ({ matches: true, media: q, addEventListener() {}, removeEventListener() {} }) // escritorio
  api.movimientos = vi.fn((limite, desplazamiento) => Promise.resolve(DATOS.slice(desplazamiento, desplazamiento + limite)))
  api.conteoPorRevisar = vi.fn().mockResolvedValue({ auto: 0, otros: 0, total: 0 })
})
afterEach(() => {
  window.matchMedia = matchOriginal
})

const montar = (ruta = '/movimientos?vista=tabla') =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[ruta]}>
        <Movimientos />
      </MemoryRouter>
    </DialogosProvider>
  )

describe('Movimientos: vista de tabla', () => {
  it('muestra las columnas pedidas y solo pinta una ventana de las 1.500 filas', async () => {
    montar()
    const tabla = await screen.findByRole('table', { name: 'Movimientos en tabla' })
    for (const t of ['Fecha', 'Descripción', 'Categoría', 'Monto']) {
      expect(within(tabla).getByRole('columnheader', { name: new RegExp(t) })).toBeInTheDocument()
    }
    const filas = tabla.querySelectorAll('tbody tr[data-fila]')
    expect(filas.length).toBeGreaterThan(0)
    expect(filas.length).toBeLessThan(200)
  })

  it('ordena por monto al tocar la columna y lo anuncia con aria-sort', async () => {
    montar()
    const tabla = await screen.findByRole('table', { name: 'Movimientos en tabla' })
    const th = within(tabla).getByRole('columnheader', { name: /Monto/ })
    expect(th).toHaveAttribute('aria-sort', 'none')
    await userEvent.click(within(th).getByRole('button'))
    expect(th).toHaveAttribute('aria-sort', 'descending')
    // Gastos con signo: «descendente» deja primero el gasto más pequeño (el menos negativo)
    const primera = tabla.querySelector('tbody tr[data-fila]')
    expect(primera.getAttribute('data-fila')).toBe('m0')
    await userEvent.click(within(th).getByRole('button'))
    expect(th).toHaveAttribute('aria-sort', 'ascending')
    expect(tabla.querySelector('tbody tr[data-fila]').getAttribute('data-fila')).not.toBe('m0')
  })

  it('permite ocultar columnas y selecciona todo con la casilla del encabezado', async () => {
    montar()
    const tabla = await screen.findByRole('table', { name: 'Movimientos en tabla' })
    // En pantallas medianas (< 1440 px) la cuenta empieza oculta; se puede mostrar y volver a ocultar
    expect(within(tabla).queryByRole('columnheader', { name: /Cuenta/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /Columnas/ }))
    await userEvent.click(screen.getByLabelText('Cuenta'))
    expect(within(tabla).getByRole('columnheader', { name: /Cuenta/ })).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('Cuenta'))
    expect(within(tabla).queryByRole('columnheader', { name: /Cuenta/ })).toBeNull()

    await userEvent.click(within(tabla).getByRole('checkbox', { name: 'Seleccionar todos los movimientos' }))
    expect(await screen.findByText(/^[0-9]+ seleccionados$/)).toBeInTheDocument()
  })

  it('en pantalla angosta ignora la vista de tabla y muestra la lista', async () => {
    window.matchMedia = (q) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
    montar()
    await screen.findByText('Compra 0000')
    expect(screen.queryByRole('table')).toBeNull()
  })
})
