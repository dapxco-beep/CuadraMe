// Volumen realista con datos 100% sintéticos (semilla fija; nada real). Comprueba que la lista de
// Movimientos no pinta las ~1.500 filas a la vez y que seguir usándola (buscar, seleccionar todo) funciona.
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const TOTAL = 1500
const CATS = ['Comida', 'Transporte', 'Ocio', 'Hogar', 'Otros']

function generar(n) {
  let semilla = 42
  const azar = () => ((semilla = (semilla * 1664525 + 1013904223) % 4294967296) / 4294967296)
  const base = new Date('2026-09-30T12:00:00')
  return Array.from({ length: n }, (_, i) => {
    const fecha = new Date(base)
    fecha.setDate(base.getDate() - Math.floor(i / 5)) // ~5 por día, del más nuevo al más viejo
    return {
      id: `m${i}`,
      descripcion: `Compra sintética ${i}`,
      categoria: CATS[Math.floor(azar() * CATS.length)],
      tipo: 'expense',
      monto: Math.round(5000 + azar() * 400000),
      fecha: fecha.toISOString(),
      cuenta_id: 'c1',
      fuente: 'manual',
      notas: '',
      cat_origen: null,
      cat_confirmada: true,
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
  const valor = { categorias: [], activas: [], nombres: ['Comida', 'Transporte', 'Ocio', 'Hogar', 'Otros'], cargando: false, recargar: () => Promise.resolve(), iconoDe: () => '💳', colorDe: () => null }
  return { useCategorias: () => valor }
})

import { DialogosProvider } from '../lib/DialogosContext'
import { vaciarCachesListas } from '../lib/useEstadoLista'
import Movimientos from '../screens/Movimientos'

beforeEach(() => {
  vaciarCachesListas()
  window.sessionStorage.clear()
  api.movimientos = vi.fn((limite, desplazamiento) => Promise.resolve(DATOS.slice(desplazamiento, desplazamiento + limite)))
  api.conteoPorRevisar = vi.fn().mockResolvedValue({ auto: 0, otros: 0, total: 0 })
})

function montar(ruta = '/movimientos') {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[ruta]}>
        <Movimientos />
      </MemoryRouter>
    </DialogosProvider>
  )
}

describe('Movimientos con volumen (1.500 sintéticos)', () => {
  it('al volver con 1.500 cargados solo pinta una ventana pequeña del DOM', async () => {
    // Se simula "volver" a una lista con 1.500 ya cargados: se piden 8 páginas de una vez
    window.sessionStorage.setItem('cuadrame:lista:/movimientos', JSON.stringify({ scroll: 0, ventana: 0, cantidad: TOTAL }))
    const t0 = performance.now()
    render(
      <DialogosProvider>
        <MemoryRouter initialEntries={['/movimientos']} initialIndex={0}>
          <Movimientos />
        </MemoryRouter>
      </DialogosProvider>
    )
    await screen.findByText('Compra sintética 0')
    await waitFor(() => expect(api.movimientos.mock.calls.length).toBeGreaterThanOrEqual(1))
    const ms = performance.now() - t0
    const filas = document.querySelectorAll('[data-fila]').length
    console.log(`[medida] primer render: ${ms.toFixed(0)} ms, filas en DOM: ${filas}`)
    expect(filas).toBeLessThan(120)
    expect(screen.queryByText('Compra sintética 1400')).toBeNull()
  })

  it('cargar todo y buscar sigue funcionando sobre los 1.500', async () => {
    montar()
    await screen.findByText('Compra sintética 0')
    for (let i = 0; i < 7; i++) {
      const antes = api.movimientos.mock.calls.length
      await userEvent.click(await screen.findByText('Cargar movimientos anteriores'))
      await waitFor(() => expect(api.movimientos.mock.calls.length).toBeGreaterThan(antes))
    }
    expect(document.querySelectorAll('[data-fila]').length).toBeLessThan(120)
    await userEvent.type(screen.getByLabelText('Buscar movimiento'), 'sintética 1499')
    expect(await screen.findByText('Compra sintética 1499', {}, { timeout: 3000 })).toBeInTheDocument()
  }, 30000)

  it('"Seleccionar todo lo filtrado" cuenta los 1.500 aunque no estén pintados', async () => {
    montar()
    await screen.findByText('Compra sintética 0')
    await userEvent.click(screen.getByText('Seleccionar'))
    await userEvent.click(await screen.findByText(/Seleccionar todo lo filtrado/))
    expect(screen.getByText(/200 seleccionados/)).toBeInTheDocument()
  })
})
