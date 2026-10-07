// Formato único de porcentajes y 'veces', Frecuentes por tipo, ayuda del botón de consentimiento
// y aviso sin metas en la hoja de reparto.
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => ({ logout: vi.fn() }) }))

import { formatPorcentaje, formatVeces } from '../lib/format'
import { pctTexto } from '../lib/informe'
import { frecuentesDelTipo } from '../screens/Agregar'
import AutorizacionTratamiento from '../screens/AutorizacionTratamiento'
import SugerenciaIngreso from '../components/SugerenciaIngreso'

describe('formato numérico único', () => {
  it('porcentajes con coma decimal y espacio', () => {
    expect(formatPorcentaje(51.1)).toBe('51,1 %')
    expect(formatPorcentaje(51.04)).toBe('51 %')
    expect(formatPorcentaje(12)).toBe('12 %')
    expect(formatPorcentaje(9, { decimales: 2 })).toBe('9 %')
    expect(formatPorcentaje(12.345, { decimales: 2 })).toBe('12,35 %')
    expect(formatPorcentaje(null)).toBe('—')
    expect(formatPorcentaje(5, { signo: true })).toBe('+5 %')
    expect(formatPorcentaje(-5, { signo: true })).toBe('-5 %')
  })
  it('Informe usa la misma función', () => {
    expect(pctTexto(51.1)).toBe('+51,1 %')
  })
  it('veces', () => {
    expect(formatVeces(1)).toBe('1 vez')
    expect(formatVeces(9)).toBe('9 veces')
    expect(formatVeces(9.04)).toBe('9 veces')
    expect(formatVeces(9.5)).toBe('9,5 veces')
  })
})

describe('Frecuentes', () => {
  it('en la pestaña Gasto no salen ingresos y al revés', () => {
    const f = [
      { descripcion: 'Nómina empresa', tipo: 'income' },
      { descripcion: 'Almuerzo', tipo: 'expense' },
    ]
    expect(frecuentesDelTipo(f, 'expense').map((x) => x.descripcion)).toEqual(['Almuerzo'])
    expect(frecuentesDelTipo(f, 'income').map((x) => x.descripcion)).toEqual(['Nómina empresa'])
  })
})

describe('consentimiento: ayuda del botón', () => {
  it('explica por qué "Aceptar y continuar" está deshabilitado', async () => {
    api.estadoConsentimientos = vi.fn().mockResolvedValue({ items: [] })
    api.consentimientos = vi.fn().mockResolvedValue({ items: [] })
    render(
      <MemoryRouter>
        <AutorizacionTratamiento onListo={() => {}} />
      </MemoryRouter>
    )
    const boton = await screen.findByRole('button', { name: 'Aceptar y continuar' })
    expect(boton).toBeDisabled()
    expect(screen.getByText('Marca la casilla obligatoria para continuar')).toBeInTheDocument()
  })
})

describe('hoja "Cómo repartir este ingreso"', () => {
  it('sin metas explica por qué no hay acción y ofrece crear una', async () => {
    api.distribuirIngreso = vi.fn().mockResolvedValue({
      monto: 3000000, necesidades: 1500000, ahorro_total: 600000, ahorro_libre: 600000, gasto_libre: 900000,
      metas: [], sobres: [], avisos: [], regla: { necesidades: 50, deseos: 30, ahorro: 20 },
    })
    render(
      <MemoryRouter>
        <SugerenciaIngreso monto={3000000} onClose={() => {}} />
      </MemoryRouter>
    )
    expect(await screen.findByText(/Aún no tienes metas a las que apartar/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Crear una meta' })).toBeInTheDocument()
    expect(screen.getByText('(50 %)')).toBeInTheDocument()
  })
})
