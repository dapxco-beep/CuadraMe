import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'

function Pantalla() {
  const volver = useVolver('/inicio-logico')
  return <button onClick={volver}>Volver</button>
}
function Donde() {
  return <p data-testid="donde">{useLocation().pathname}</p>
}

function App({ entradas }) {
  return (
    <MemoryRouter initialEntries={entradas}>
      <Routes>
        <Route path="/" element={<Link to="/detalle">Ir</Link>} />
        <Route path="/detalle" element={<Pantalla />} />
        <Route path="/inicio-logico" element={<p>Inicio lógico</p>} />
      </Routes>
      <Donde />
    </MemoryRouter>
  )
}

describe('useVolver', () => {
  it('con historial interno vuelve a la pantalla anterior (navigate(-1))', async () => {
    render(<App entradas={['/']} />)
    await userEvent.click(screen.getByText('Ir'))
    expect(screen.getByTestId('donde')).toHaveTextContent('/detalle')
    await userEvent.click(screen.getByText('Volver'))
    expect(screen.getByTestId('donde')).toHaveTextContent('/')
    expect(screen.getByText('Ir')).toBeInTheDocument()
  })

  it('sin historial (entrada directa) va a la ruta por defecto', async () => {
    render(<App entradas={['/detalle']} />)
    await userEvent.click(screen.getByText('Volver'))
    expect(screen.getByTestId('donde')).toHaveTextContent('/inicio-logico')
    expect(screen.getByText('Inicio lógico')).toBeInTheDocument()
  })

  it('la ruta por defecto se pone con replace: no queda la pantalla de entrada en el historial', async () => {
    render(<App entradas={['/detalle']} />)
    await userEvent.click(screen.getByText('Volver'))
    // Un segundo "atrás" no tiene a dónde ir: seguimos en la ruta lógica
    expect(screen.getByTestId('donde')).toHaveTextContent('/inicio-logico')
  })
})
