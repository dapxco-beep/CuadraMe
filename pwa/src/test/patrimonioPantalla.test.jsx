import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Patrimonio from '../screens/Patrimonio'

const RESUMEN = {
  moneda_base: 'COP',
  patrimonio_neto: 25_000_000,
  total_activos: 24_000_000,
  total_cuentas: 2_000_000,
  total_deudas: 1_000_000,
  variacion_mes_anterior: 500_000,
  distribucion: [
    { clase: 'inmueble', valor: 20_000_000, pct: 76.9 },
    { clase: 'etf', valor: 4_000_000, pct: 15.4 },
    { clase: 'cuentas', valor: 2_000_000, pct: 7.7 },
  ],
  historial: [
    { mes: '2026-09', patrimonio_neto: 24_500_000 },
    { mes: '2026-10', patrimonio_neto: 25_000_000 },
  ],
  pasivos: [{ id: 'd1', nombre: 'Tarjeta Visa', entidad: 'Bancolombia', saldo: 1_000_000 }],
  activos: [
    {
      id: 'a1', clase: 'etf', nombre: 'VOO', ticker: 'VOO', moneda: 'USD', valor: 1000, valor_cop: 4_000_000,
      costo: 900, ganancia: 100, rentabilidad_pct: 11.1, xirr_pct: 14.2, precio_fecha: '2026-10-01T00:00:00',
      unidades: 10, costo_promedio: 90, precio_actual: 100,
    },
    {
      id: 'a2', clase: 'cdt', nombre: 'CDT Davivienda', moneda: 'COP', valor: 11_200_000, valor_cop: 11_200_000,
      costo: 10_000_000, ganancia: 1_200_000, rentabilidad_pct: 12, xirr_pct: 12, tasa_ea: 12,
      dias_al_vencimiento: 200, vencido: false, valor_vencimiento: 11_900_000,
      capital: 10_000_000, fecha_inicio: '2025-10-01T00:00:00', fecha_vencimiento: '2026-12-01T00:00:00',
    },
  ],
}

function montar() {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter>
          <Patrimonio />
        </MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    patrimonio: vi.fn().mockResolvedValue(RESUMEN),
    crearActivo: vi.fn().mockResolvedValue({}),
    editarActivo: vi.fn().mockResolvedValue({}),
    eliminarActivo: vi.fn().mockResolvedValue({ ok: true }),
  })
})

describe('Patrimonio', () => {
  it('muestra patrimonio neto, activos con rentabilidad y pasivos', async () => {
    montar()
    expect(await screen.findByText('Patrimonio neto')).toBeInTheDocument()
    expect(screen.getAllByText(/25\.000\.000/).length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Editar VOO')).toBeInTheDocument()
    expect(screen.getByText(/\+11,1 %/)).toBeInTheDocument()
    expect(screen.getByText(/XIRR \+14,2 % E\.A\./)).toBeInTheDocument()
    expect(screen.getByText(/CDT Davivienda/)).toBeInTheDocument()
    expect(screen.getByText('Tarjeta Visa')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Evolución del patrimonio/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Distribución/ })).toBeInTheDocument()
  })

  it('muestra error con reintento si la API falla', async () => {
    api.patrimonio.mockRejectedValueOnce(new Error('Sin conexión'))
    montar()
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión')
    await userEvent.click(screen.getByText('Reintentar'))
    expect(await screen.findByText('Patrimonio neto')).toBeInTheDocument()
  })

  it('estado vacío invita a agregar el primer activo', async () => {
    api.patrimonio.mockResolvedValue({
      ...RESUMEN, activos: [], pasivos: [], distribucion: [], historial: [], total_cuentas: 0,
      patrimonio_neto: 0, total_activos: 0, total_deudas: 0, variacion_mes_anterior: null,
    })
    montar()
    expect(await screen.findByText(/Aún no hay nada que contar/)).toBeInTheDocument()
  })

  it('crea un CDT con vista previa del valor al vencimiento', async () => {
    montar()
    await screen.findByText('Patrimonio neto')
    await userEvent.click(screen.getByLabelText('Agregar activo'))
    await userEvent.type(screen.getByPlaceholderText(/CDT Bancolombia/), 'Mi CDT')
    const [capital, tasa] = screen.getAllByRole('textbox').slice(1)
    await userEvent.type(capital, '1000000')
    await userEvent.type(tasa, '12')
    const fechas = document.querySelectorAll('input[type="date"]')
    await userEvent.clear(fechas[0])
    await userEvent.type(fechas[0], '2025-01-01')
    await userEvent.type(fechas[1], '2026-01-01')
    expect(await screen.findByText(/Al vencimiento/)).toHaveTextContent(/1\.120\.000/)
    await userEvent.click(screen.getAllByRole('button', { name: 'Agregar activo' }).at(-1))
    await waitFor(() => expect(api.crearActivo).toHaveBeenCalled())
    expect(api.crearActivo.mock.calls[0][0]).toMatchObject({
      clase: 'cdt', nombre: 'Mi CDT', capital: 1000000, tasa_ea: 12, moneda: 'COP',
    })
  })

  it('valida campos obligatorios antes de llamar a la API', async () => {
    montar()
    await screen.findByText('Patrimonio neto')
    await userEvent.click(screen.getByLabelText('Agregar activo'))
    await userEvent.click(screen.getAllByRole('button', { name: 'Agregar activo' }).at(-1))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ponle un nombre')
    expect(api.crearActivo).not.toHaveBeenCalled()
  })

  it('edita un activo existente', async () => {
    montar()
    await userEvent.click(await screen.findByLabelText('Editar VOO'))
    expect(screen.getByText('Editar activo')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
    await waitFor(() => expect(api.editarActivo).toHaveBeenCalledWith('a1', expect.objectContaining({
      clase: 'etf', unidades: 10, costo_promedio: 90, precio_actual: 100, moneda: 'USD',
    })))
  })
})
