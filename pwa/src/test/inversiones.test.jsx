import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import { ThemeProvider } from '../lib/ThemeContext'
import Inversiones from '../screens/Inversiones'
import { haceCuanto, hayConcentracion, pctTexto, textoEstadoPrecio } from '../lib/inversiones'

const POS = {
  id: 'p1', broker_id: 'b1', nombre: 'Ecopetrol', ticker: 'ECOPETROL', moneda: 'COP', tipo: 'accion',
  cantidad: 100, precio: 2000, valor: 200000, valor_cop: 200000, no_realizada: 20000, no_realizada_pct: 11.1,
  precio_estado: 'retrasado', precio_mensaje: 'Precio de hace 3 días',
}
const DATOS = {
  tiene: true, valor_total: 200000, costo_total: 180000, aportado: 180000, no_realizada: 20000, no_realizada_pct: 11.1,
  dividendos: 0, hoy_cop: null, tir_pct: null, sin_precio: [], evolucion: [],
  periodos: { ytd_pct: null, doce_meses_pct: null, desde_inicio_pct: 11.1 },
  brokers: [{ id: 'b1', nombre: 'Trii', valor_cop: 200000, posiciones: [POS] }],
  posiciones: [POS],
  distribucion_broker: [{ clase: 'Trii', valor: 200000, pct: 100 }], distribucion_tipo: [], distribucion_moneda: [],
  concentracion: { nombre: 'Ecopetrol', pct: 100, valor: 200000 },
}

function montar() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <Inversiones />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('Inversiones', () => {
  beforeEach(() => {
    Object.keys(api).forEach((k) => delete api[k])
    api.opcionesInversiones = vi.fn().mockResolvedValue({ resumen_semanal: false })
  })

  it('sin posiciones muestra un estado vacío amable y opcional', async () => {
    api.inversiones = vi.fn().mockResolvedValue({ tiene: false, posiciones: [], brokers: [] })
    montar()
    expect(await screen.findByTestId('inversiones-vacio')).toBeInTheDocument()
    expect(screen.getByText(/opcional/i)).toBeInTheDocument()
  })

  it('muestra resumen, broker con posición y el estado honesto del precio', async () => {
    api.inversiones = vi.fn().mockResolvedValue(DATOS)
    montar()
    expect(await screen.findByText('Ecopetrol')).toBeInTheDocument()
    expect(screen.getAllByText('Trii').length).toBeGreaterThan(0)
    expect(screen.getByText('Precio de hace 3 días')).toBeInTheDocument()
    expect(screen.getAllByText(/no es asesoría/i).length).toBeGreaterThan(0)
  })

  it('«Actualizar ahora» muestra el mensaje del tope', async () => {
    api.inversiones = vi.fn().mockResolvedValue(DATOS)
    api.actualizarPreciosInversiones = vi.fn().mockResolvedValue({ mensaje: 'Llegaste al máximo de actualizaciones de hoy' })
    montar()
    await userEvent.click(await screen.findByRole('button', { name: /actualizar ahora/i }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/máximo/))
  })
})

describe('lib/inversiones', () => {
  it('formatea y avisa', () => {
    expect(pctTexto(12.34)).toBe('+12,3 %')
    expect(pctTexto(null)).toBe('—')
    expect(hayConcentracion({ pct: 55 }, 3)).toBe(true)
    expect(hayConcentracion({ pct: 55 }, 1)).toBe(false)
    expect(textoEstadoPrecio({ precio: null })).toMatch(/sin precio/i)
    expect(haceCuanto('2026-10-01T00:00:00', new Date('2026-10-04T12:00:00'))).toBe('hace 3 días')
  })
})
