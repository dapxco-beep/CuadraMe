// Un gasto de las 9 p. m. en Bogotá llega como el día siguiente en UTC: debe quedar en SU día, no en el siguiente.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { claveDia, etiquetaDia } from '../lib/fechaMovimiento'

const CUENTAS = [{ id: 'c1', nombre: 'Bancolombia', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]
const MOVS = [
  // 8 oct, 9:00 p. m. en Bogotá = 9 oct 02:00 UTC
  { id: 'm1', cuenta_id: 'c1', fecha: '2026-10-09T02:00:00Z', descripcion: 'Cena nocturna', categoria: 'Comida', tipo: 'expense', monto: 40000, fuente: 'manual', notas: '' },
  { id: 'm2', cuenta_id: 'c1', fecha: '2026-10-09T15:00:00Z', descripcion: 'Almuerzo', categoria: 'Comida', tipo: 'expense', monto: 20000, fuente: 'manual', notas: '' },
]

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => ({ usuario: { id: 'u1', email: 'l@test.com' } }) }))
vi.mock('../lib/CuentasContext', () => ({ useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }) }))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ categorias: [], nombres: ['Comida'], cargando: false, recargar: vi.fn(), iconoDe: () => '🍽️' }),
}))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import Movimientos from '../screens/Movimientos'

describe('día de un movimiento (America/Bogota)', () => {
  it('claveDia: 9 p. m. de Bogotá (02:00 UTC del día siguiente) es del día de Bogotá', () => {
    expect(claveDia('2026-10-09T02:00:00Z')).toBe('2026-10-08')
    expect(claveDia('2026-10-09T15:00:00Z')).toBe('2026-10-09')
    expect(claveDia('2026-10-09T02:00:00+00:00')).toBe('2026-10-08')
  })

  it('una fecha «de pared» o solo día no se corre', () => {
    expect(claveDia('2026-10-08')).toBe('2026-10-08')
    expect(claveDia('2026-10-08T21:00:00')).toBe('2026-10-08')
  })

  it('etiquetaDia: Hoy y Ayer se cuentan en hora de Bogotá', () => {
    const ahora = new Date('2026-10-09T17:00:00Z') // 9 oct, 12:00 en Bogotá
    expect(etiquetaDia('2026-10-09T02:00:00Z', ahora)).toBe('Ayer')
    expect(etiquetaDia('2026-10-09T15:00:00Z', ahora)).toBe('Hoy')
    expect(etiquetaDia('2026-10-05T15:00:00Z', ahora)).toMatch(/5 de octubre/)
  })
})

describe('Movimientos agrupa por día de Bogotá', () => {
  beforeEach(() => {
    localStorage.clear()
    Object.assign(api, {
      movimientos: vi.fn().mockResolvedValue(MOVS),
      cuentas: vi.fn().mockResolvedValue(CUENTAS),
      gmailEstado: vi.fn().mockResolvedValue({ conectado: false }),
      correosPendientes: vi.fn().mockResolvedValue([]),
      sincronizacionEstado: vi.fn().mockResolvedValue({ tareas: [] }),
    })
  })

  it('la cena de las 9 p. m. cae en el día 8 y el almuerzo en el 9 (dos grupos, no uno)', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-20T17:00:00Z'))
    render(
      <ThemeProvider>
        <DialogosProvider>
          <MemoryRouter>
            <Movimientos />
          </MemoryRouter>
        </DialogosProvider>
      </ThemeProvider>
    )
    vi.useRealTimers()
    expect(await screen.findByText('Cena nocturna')).toBeInTheDocument()
    expect(screen.getByText('8 de octubre')).toBeInTheDocument()
    expect(screen.getByText('9 de octubre')).toBeInTheDocument()
  })
})
