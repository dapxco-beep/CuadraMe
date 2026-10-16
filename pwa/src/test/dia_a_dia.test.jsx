import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from './userEvent.js'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import DiaADia, { agruparSemanas } from '../components/DiaADia'

const DIAS = [
  { dia: '2026-10-05', gasto: 0, ingreso: 0, disponible: 1000000 },
  { dia: '2026-10-06', gasto: 40000, ingreso: 0, disponible: 960000 },
  { dia: '2026-10-07', gasto: 10000, ingreso: 500000, disponible: 1450000 },
]

beforeEach(() => {
  api.gastoDiario = vi.fn().mockResolvedValue({ desde: '2026-10-05', hasta: '2026-10-07', total: 50000, disponible_hoy: 1450000, dias: DIAS })
})

describe('Día a día (En qué gasto)', () => {
  it('resume el gasto por día y deja ver cuánto te queda', async () => {
    render(<DiaADia desde="2026-10-05" hasta="2026-10-07" />)
    expect(api.gastoDiario).toHaveBeenCalledWith('2026-10-05', '2026-10-07')
    const resumen = await screen.findByTestId('resumen-gasto')
    expect(resumen).toHaveTextContent('promedio')
    expect(resumen).toHaveTextContent('1 día sin gastar')
    // por defecto muestra el último día
    expect(screen.getByTestId('dia-elegido')).toHaveTextContent('Gastaste')

    await userEvent.click(screen.getByRole('button', { name: 'Lo que te queda' }))
    const disp = screen.getByTestId('resumen-disponible')
    expect(disp).toHaveTextContent('Hoy tienes')
    expect(disp).toHaveTextContent('subió')
    expect(disp).toHaveTextContent('tu punto más bajo')
    expect(screen.getByTestId('dia-elegido')).toHaveTextContent('Tenías')
  })

  it('las flechas recorren los días y se frenan en los extremos', async () => {
    render(<DiaADia desde="2026-10-05" hasta="2026-10-07" />)
    await screen.findByTestId('dia-a-dia')
    const siguiente = screen.getByRole('button', { name: 'Día siguiente' })
    const anterior = screen.getByRole('button', { name: 'Día anterior' })
    expect(siguiente).toBeDisabled()
    await userEvent.click(anterior)
    await userEvent.click(anterior)
    expect(anterior).toBeDisabled()
    expect(within(screen.getByTestId('dia-elegido')).getByText(/Gastaste/)).toHaveTextContent('Gastaste')
  })

  it('agrupa por semanas (lunes a domingo) cuando el periodo es largo', () => {
    const dias = Array.from({ length: 14 }, (_, i) => ({ dia: `2026-10-${String(5 + i).padStart(2, '0')}`, gasto: 100, ingreso: 0, disponible: 1000 - i }))
    const sem = agruparSemanas(dias)
    expect(sem).toHaveLength(2)
    expect(sem[0]).toMatchObject({ dia: '2026-10-05', gasto: 700, semana: true, disponible: 994 })
  })

  it('si falla la carga lo dice sin romper la pantalla', async () => {
    api.gastoDiario.mockRejectedValueOnce(new Error('Sin conexión'))
    render(<DiaADia desde="2026-10-05" hasta="2026-10-07" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión')
  })
})
