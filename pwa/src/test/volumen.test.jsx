// Volumen realista con datos 100% sintéticos (generados con una semilla fija; nada real).
// Comprueba que la lista de Movimientos no pinta las ~1.500 filas a la vez, que los filtros
// siguen funcionando y que "volver" desde el detalle conserva lo que la persona tenía puesto.
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const TOTAL = 1500
const CATS = ['Mercado', 'Transporte', 'Restaurantes', 'Servicios', 'Salud', 'Ocio', 'Nómina']

function generar(n) {
  let semilla = 42
  const azar = () => ((semilla = (semilla * 1664525 + 1013904223) % 4294967296) / 4294967296)
  const base = new Date('2026-09-30T12:00:00')
  return Array.from({ length: n }, (_, i) => {
    const fecha = new Date(base)
    fecha.setDate(base.getDate() - Math.floor(i / 5)) // ~5 movimientos por día, ordenados de nuevo a viejo
    const cat = CATS[Math.floor(azar() * CATS.length)]
    return {
      id: `m${i}`,
      descripcion: `Compra sintética ${i}`,
      categoria: cat,
      tipo: cat === 'Nómina' ? 'income' : 'expense',
      monto: Math.round(5000 + azar() * 400000),
      fecha: fecha.toISOString(),
      cuenta_id: 'c1',
    }
  })
}
const DATOS = generar(TOTAL)

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Efectivo', moneda: 'COP' }] }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Mercado'], iconoDe: () => '💳' }),
}))
vi.mock('../lib/DialogosContext', () => ({ useDialogos: () => ({ avisar: vi.fn() }) }))

import Movimientos from '../screens/Movimientos'
import { GraficoBarras, Sparkline, BarraProgreso } from '../components/graficos'

beforeEach(() => {
  sessionStorage.clear()
  api.movimientos = vi.fn((limite, desplazamiento) => Promise.resolve(DATOS.slice(desplazamiento, desplazamiento + limite)))
})

function montar() {
  return render(
    <MemoryRouter>
      <Movimientos />
    </MemoryRouter>
  )
}

describe('Movimientos con volumen', () => {
  it('con 1.500 filas cargadas solo pinta una ventana pequeña del DOM', async () => {
    montar()
    await screen.findByText('Compra sintética 0')
    // Cargar todas las páginas
    for (let i = 0; i < 7; i++) {
      const boton = screen.queryByText('Cargar movimientos anteriores')
      if (!boton) break
      const antes = api.movimientos.mock.calls.length
      await userEvent.click(boton)
      await waitFor(() => expect(api.movimientos.mock.calls.length).toBeGreaterThan(antes))
    }
    await waitFor(() => expect(api.movimientos).toHaveBeenCalledTimes(Math.ceil(TOTAL / 200) + 0))
    const enlaces = screen.getAllByRole('link')
    expect(enlaces.length).toBeLessThan(60)
    expect(screen.queryByText('Compra sintética 1400')).toBeNull()
  })

  it('mide el tiempo de render inicial (referencia)', async () => {
    const t0 = performance.now()
    montar()
    await screen.findByText('Compra sintética 0')
    const ms = performance.now() - t0
    console.log(`[medida] primer render con 200 filas: ${ms.toFixed(0)} ms, enlaces en DOM: ${screen.getAllByRole('link').length}`)
    expect(ms).toBeLessThan(3000)
  })

  it('el buscador filtra sobre todo lo cargado', async () => {
    montar()
    await screen.findByText('Compra sintética 0')
    await userEvent.type(screen.getByLabelText('Buscar movimiento'), 'sintética 7')
    await waitFor(() => expect(screen.queryByText('Compra sintética 0')).toBeNull())
    expect(screen.getByText('Compra sintética 7')).toBeInTheDocument()
  })

  it('al volver desde el detalle conserva el filtro', async () => {
    const primera = montar()
    await screen.findByText('Compra sintética 0')
    await userEvent.type(screen.getByLabelText('Buscar movimiento'), 'sintética 7')
    await userEvent.click(await screen.findByText('Compra sintética 7'))
    primera.unmount()

    montar()
    expect(screen.getByLabelText('Buscar movimiento')).toHaveValue('sintética 7')
    expect(await screen.findByText('Compra sintética 7')).toBeInTheDocument()
  })

  it('muestra esqueleto mientras carga', () => {
    api.movimientos = vi.fn(() => new Promise(() => {}))
    montar()
    expect(screen.getByRole('status', { name: 'Cargando movimientos' })).toHaveAttribute('aria-busy', 'true')
  })
})

describe('Gráficas unificadas', () => {
  it('las barras traen resumen en texto y etiqueta accesible por mes', () => {
    render(
      <GraficoBarras
        titulo="Ingresos y gastos"
        series={[{ nombre: 'Ingresos', color: 'var(--color-accent-2)' }, { nombre: 'Gastos', color: 'var(--color-ink)' }]}
        datos={[{ clave: '2026-09', etiqueta: 'Sep', valores: [1000000, 400000] }]}
      />
    )
    const grupo = screen.getByRole('group', { name: 'Ingresos y gastos' })
    expect(within(grupo).getByRole('button', { name: /Sep: ingresos .*gastos/ })).toBeInTheDocument()
  })

  it('sin datos muestra un estado vacío claro, no una gráfica en blanco', () => {
    render(<GraficoBarras titulo="x" series={[{ nombre: 'A', color: 'red' }]} datos={[{ clave: 'a', etiqueta: 'A', valores: [0] }]} />)
    expect(screen.getByText(/Aún no hay datos/)).toBeInTheDocument()
  })

  it('la sparkline describe hacia dónde va el valor', () => {
    render(<Sparkline etiqueta="Saldo proyectado" valores={[100, 200, 300]} />)
    expect(screen.getByRole('img', { name: /Saldo proyectado: sube/ })).toBeInTheDocument()
  })

  it('la barra de avance expone su valor', () => {
    render(<BarraProgreso pct={72.4} etiqueta="Mercado" />)
    expect(screen.getByRole('progressbar', { name: 'Mercado' })).toHaveAttribute('aria-valuenow', '72')
  })
})
