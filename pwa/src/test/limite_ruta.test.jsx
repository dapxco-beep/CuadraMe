import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import LimiteRuta from '../components/LimiteRuta'

function Rota() {
  throw new Error('pantalla rota')
}

function App({ inicial = '/rota' }) {
  return (
    <MemoryRouter initialEntries={[inicial]}>
      <nav aria-label="Navegación principal">menú</nav>
      <LimiteRuta>
        <Routes>
          <Route path="/" element={<p>Pantalla de inicio</p>} />
          <Route path="/rota" element={<Rota />} />
        </Routes>
      </LimiteRuta>
    </MemoryRouter>
  )
}

describe('LimiteRuta', () => {
  it('si una pantalla falla, la navegación sigue visible y «Volver al inicio» funciona', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const mudo = (e) => e.preventDefault() // jsdom reporta el error lanzado; el límite ya lo atrapa
    window.addEventListener('error', mudo)
    render(<App />)
    expect(screen.getByTestId('limite-ruta')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Navegación principal' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Reintentar/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Volver al inicio' }))
    expect(screen.getByText('Pantalla de inicio')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Navegación principal' })).toBeInTheDocument()
    window.removeEventListener('error', mudo)
    spy.mockRestore()
  })
})
