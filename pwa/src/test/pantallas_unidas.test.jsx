import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import ATab from '../components/ATab'
import AInformes from '../components/AInformes'
import { PESTANAS_PLAN } from '../screens/PresupuestoPlan'
import { PESTANAS_AHORRO } from '../screens/MetasAhorro'
import { PESTANAS_CUENTAS } from '../screens/MisCuentas'
import { PESTANAS_AYUDA } from '../screens/AyudaAprende'
import { PESTANAS } from '../screens/Informes'
import PantallaConPestanas from '../components/PantallaConPestanas'

function Donde() {
  const { pathname, search } = useLocation()
  return <p data-testid="donde">{pathname + search}</p>
}

function montar(inicial) {
  return render(
    <MemoryRouter initialEntries={[inicial]}>
      <Routes>
        <Route path="/recurrentes" element={<ATab a="/presupuesto" tab="fijos" />} />
        <Route path="/inversiones" element={<ATab a="/metas" tab="inversiones" />} />
        <Route path="/deudas" element={<ATab a="/cuentas" tab="deudas" />} />
        <Route path="/aprende" element={<ATab a="/ayuda" tab="aprende" />} />
        <Route path="/impuestos" element={<AInformes tab="impuestos" />} />
        <Route path="*" element={<Donde />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('Pantallas unidas: los enlaces de siempre siguen funcionando', () => {
  it.each([
    ['/recurrentes', '/presupuesto?tab=fijos'],
    ['/inversiones', '/metas?tab=inversiones'],
    ['/deudas', '/cuentas?tab=deudas'],
    ['/aprende', '/ayuda?tab=aprende'],
    ['/impuestos', '/informes?tab=impuestos'],
  ])('%s lleva a %s', (vieja, nueva) => {
    montar(vieja)
    expect(screen.getByTestId('donde')).toHaveTextContent(nueva)
  })

  it('conserva el resto de la consulta (p. ej. el año)', () => {
    montar('/impuestos?anio=2025')
    expect(screen.getByTestId('donde').textContent).toContain('anio=2025')
    expect(screen.getByTestId('donde').textContent).toContain('tab=impuestos')
  })
})

describe('Pestañas de las pantallas unidas', () => {
  it('cada una trae sus pestañas', () => {
    expect(PESTANAS_PLAN.map((p) => p.id)).toEqual(['presupuesto', 'fijos'])
    expect(PESTANAS_AHORRO.map((p) => p.id)).toEqual(['metas', 'inversiones'])
    expect(PESTANAS_CUENTAS.map((p) => p.id)).toEqual(['cuentas', 'deudas'])
    expect(PESTANAS_AYUDA.map((p) => p.id)).toEqual(['ayuda', 'aprende'])
    expect(PESTANAS.map((p) => p.id)).toContain('impuestos')
  })
})

describe('PantallaConPestanas como pantalla raíz', () => {
  const A = () => <p>Pantalla A</p>
  const B = () => <p>Pantalla B</p>
  const pestanas = [{ id: 'a', texto: 'Uno', Pantalla: A }, { id: 'b', texto: 'Dos', Pantalla: B }]

  it('sin «raiz» tiene flecha de volver; con «raiz» no', () => {
    const { unmount } = render(<MemoryRouter><PantallaConPestanas titulo="Algo" pestanas={pestanas} /></MemoryRouter>)
    expect(screen.getByRole('button', { name: 'Volver' })).toBeInTheDocument()
    unmount()
    render(<MemoryRouter><PantallaConPestanas titulo="Algo" pestanas={pestanas} raiz /></MemoryRouter>)
    expect(screen.queryByRole('button', { name: 'Volver' })).toBeNull()
  })

  it('cambiar de pestaña muestra su pantalla', async () => {
    render(<MemoryRouter><PantallaConPestanas titulo="Algo" pestanas={pestanas} raiz /></MemoryRouter>)
    expect(screen.getByText('Pantalla A')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'Dos' }))
    expect(screen.getByText('Pantalla B')).toBeInTheDocument()
  })
})
