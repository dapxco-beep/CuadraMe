import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const Marca = (nombre) => function Pantalla() {
  const { search } = useLocation()
  return <div>{`PANTALLA-${nombre}|${search}`}</div>
}
vi.mock('../screens/Categorias', () => ({ default: Marca('CATEGORIAS') }))
vi.mock('../screens/ReglasCategoria', () => ({ default: Marca('REGLAS') }))
vi.mock('../screens/PorCategorizar', () => ({ default: Marca('PENDIENTES') }))
vi.mock('../screens/RevisarTraslados', () => ({ default: Marca('TRASLADOS') }))
vi.mock('../screens/BuscarDuplicados', () => ({ default: Marca('REPETIDOS') }))

import OrdenarCategorias from '../screens/OrdenarCategorias'
import RevisarMovimientos from '../screens/RevisarMovimientos'
import ATab from '../components/ATab'

const montar = (ruta) =>
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/categorias" element={<OrdenarCategorias />} />
        <Route path="/reglas-categoria" element={<ATab a="/categorias" tab="reglas" />} />
        <Route path="/categorizar" element={<ATab a="/categorias" tab="pendientes" />} />
        <Route path="/revisar" element={<RevisarMovimientos />} />
        <Route path="/traslados" element={<ATab a="/revisar" tab="traslados" />} />
        <Route path="/buscar-duplicados" element={<ATab a="/revisar" tab="repetidos" />} />
      </Routes>
    </MemoryRouter>
  )

describe('Categorías: tres pantallas en una', () => {
  it('abre en «Categorías» con sus tres pestañas y cambia al tocar', async () => {
    const user = userEvent.setup()
    montar('/categorias')
    expect(await screen.findByText(/PANTALLA-CATEGORIAS/)).toBeInTheDocument()
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Categorías', 'Reglas', 'Por categorizar'])
    await user.click(screen.getByRole('tab', { name: 'Reglas' }))
    expect(await screen.findByText(/PANTALLA-REGLAS/)).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Reglas' })).toHaveAttribute('aria-selected', 'true')
  })
  it.each([['/reglas-categoria', 'REGLAS'], ['/categorizar', 'PENDIENTES']])('%s lleva a su pestaña', async (ruta, marca) => {
    montar(ruta)
    expect(await screen.findByText(new RegExp(`PANTALLA-${marca}`))).toBeInTheDocument()
  })
})

describe('Revisar movimientos: traslados y repetidos en una', () => {
  it('abre en «Entre mis cuentas» y cambia a «Repetidos»', async () => {
    const user = userEvent.setup()
    montar('/revisar')
    expect(await screen.findByText(/PANTALLA-TRASLADOS/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Revisar movimientos', level: 1 })).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Repetidos' }))
    expect(await screen.findByText(/PANTALLA-REPETIDOS/)).toBeInTheDocument()
  })
  it.each([['/traslados', 'TRASLADOS'], ['/buscar-duplicados', 'REPETIDOS']])('%s lleva a su pestaña y conserva la consulta', async (ruta, marca) => {
    montar(`${ruta}?desde=2026-10-01`)
    const el = await screen.findByText(new RegExp(`PANTALLA-${marca}`))
    expect(el.textContent).toContain('desde=2026-10-01')
  })
})
