import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

// Las cinco pantallas de «cómo voy» se sustituyen por marcadores: aquí se prueba la unión, no cada pantalla.
const Marca = (nombre) => function Pantalla() {
  const { search } = useLocation()
  return <div>{`PANTALLA-${nombre}|${search}`}</div>
}
vi.mock('../screens/Informe', () => ({ default: Marca('GASTOS') }))
vi.mock('../screens/Wrapped', () => ({ default: Marca('MIMES') }))
vi.mock('../screens/Insights', () => ({ default: Marca('DIAS') }))
vi.mock('../screens/Patrimonio', () => ({ default: Marca('PATRIMONIO') }))
vi.mock('../screens/CierreMes', () => ({ default: Marca('CIERRE') }))

import Informes from '../screens/Informes'
import AInformes from '../components/AInformes'

const montar = (ruta) =>
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/informes" element={<Informes />} />
        <Route path="/informe" element={<AInformes tab="gastos" />} />
        <Route path="/resumen" element={<AInformes tab="resumen" />} />
        <Route path="/insights" element={<AInformes tab="dias" />} />
        <Route path="/patrimonio" element={<AInformes tab="patrimonio" />} />
        <Route path="/cierre-mes" element={<AInformes tab="cierre" />} />
        <Route path="/mi-cuenta-cuadra" element={<AInformes tab="cierre" />} />
      </Routes>
    </MemoryRouter>
  )

describe('Informes: una pantalla con pestañas', () => {
  it('sin pestaña elegida abre «Gastos» y muestra las cinco pestañas', async () => {
    montar('/informes')
    expect(await screen.findByText(/PANTALLA-GASTOS/)).toBeInTheDocument()
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Gastos', 'Mi mes', 'Días', 'Patrimonio', 'Cierre'])
    expect(screen.getByRole('tab', { name: 'Gastos' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('heading', { name: 'Informes', level: 1 })).toBeInTheDocument()
  })

  it('tocar una pestaña cambia el contenido y la marca como activa', async () => {
    const user = userEvent.setup()
    montar('/informes')
    await screen.findByText(/PANTALLA-GASTOS/)
    await user.click(screen.getByRole('tab', { name: 'Cierre' }))
    expect(await screen.findByText(/PANTALLA-CIERRE/)).toBeInTheDocument()
    expect(screen.queryByText(/PANTALLA-GASTOS/)).toBeNull()
    expect(screen.getByRole('tab', { name: 'Cierre' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Gastos' })).toHaveAttribute('aria-selected', 'false')
  })

  it('una pestaña desconocida cae en «Gastos»', async () => {
    montar('/informes?tab=inventada')
    expect(await screen.findByText(/PANTALLA-GASTOS/)).toBeInTheDocument()
  })
})

describe('Los enlaces viejos llevan a su pestaña y conservan la consulta', () => {
  it.each([
    ['/informe', 'GASTOS'],
    ['/resumen', 'MIMES'],
    ['/insights', 'DIAS'],
    ['/patrimonio', 'PATRIMONIO'],
    ['/cierre-mes', 'CIERRE'],
    ['/mi-cuenta-cuadra', 'CIERRE'],
  ])('%s -> pestaña %s', async (ruta, marca) => {
    montar(ruta)
    expect(await screen.findByText(new RegExp(`PANTALLA-${marca}`))).toBeInTheDocument()
  })

  it('el periodo elegido en el enlace no se pierde', async () => {
    montar('/informe?periodo=30_dias')
    const marca = await screen.findByText(/PANTALLA-GASTOS/)
    expect(marca.textContent).toContain('periodo=30_dias')
    expect(marca.textContent).toContain('tab=gastos')
  })
})
