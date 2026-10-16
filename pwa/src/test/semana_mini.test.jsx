import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import SemanaMini from '../components/SemanaMini'
import DiaADia from '../components/DiaADia'

const dias = (gastos) => gastos.map((g, i) => ({ dia: `2026-10-${String(9 + i).padStart(2, '0')}`, gasto: g, ingreso: 0, disponible: 1000 }))

beforeEach(() => {
  api.gastoDiario = vi.fn()
})

describe('Mini gráfico de la semana (Inicio)', () => {
  it('muestra 7 barras que llevan a En qué gasto', async () => {
    api.gastoDiario.mockResolvedValue({ dias: dias([0, 100, 0, 300, 50, 0, 200]) })
    render(<MemoryRouter><SemanaMini /></MemoryRouter>)
    const enlace = await screen.findByTestId('semana-mini')
    expect(enlace).toHaveAttribute('href', '/informe')
    expect(enlace.querySelectorAll('span[aria-hidden="true"]')).toHaveLength(7)
  })

  it('sin gastos, sin datos o con error no ocupa lugar ni rompe', async () => {
    api.gastoDiario.mockResolvedValue({ dias: dias([0, 0, 0, 0, 0, 0, 0]) })
    const { container, rerender } = render(<MemoryRouter><SemanaMini /></MemoryRouter>)
    await vi.waitFor(() => expect(api.gastoDiario).toHaveBeenCalled())
    expect(container.querySelector('[data-testid="semana-mini"]')).toBeNull()
    api.gastoDiario = undefined // ni siquiera existe: el fallo se absorbe
    rerender(<MemoryRouter><SemanaMini key="otra" /></MemoryRouter>)
    expect(screen.queryByTestId('semana-mini')).toBeNull()
  })
})

describe('Día a día: tope de 400 días', () => {
  it('si el periodo es más largo, pide solo los últimos 400 días', async () => {
    api.gastoDiario.mockResolvedValue({ dias: dias([10]), disponible_hoy: 0 })
    render(<DiaADia desde="2024-01-01" hasta="2026-10-15" />)
    await screen.findByTestId('dia-a-dia')
    const [desde, hasta] = api.gastoDiario.mock.calls[0]
    expect(hasta).toBe('2026-10-15')
    expect(desde).toBe('2025-09-11') // 399 días antes
  })
})
