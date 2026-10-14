import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import IngresosGastos from '../components/IngresosGastos'

const fmt = (v) => `$${Math.round(v).toLocaleString('es-CO')}`
const DATOS = {
  ingresos: 3_000_000, gastos: 1_000_000, balance: 2_000_000, tasa_ahorro: 66.7, hay_datos: true,
  anterior: { etiqueta: 'septiembre de 2026', ingresos: 2_000_000, gastos: 2_500_000, balance: -500_000 },
  variacion: { ingresos_pct: 50, gastos_pct: -60, balance_pct: 500, tasa_ahorro_puntos: null },
  meses: [
    { mes: '2026-09', etiqueta: 'sep', etiqueta_larga: 'septiembre de 2026', ingresos: 2_000_000, gastos: 2_500_000, balance: -500_000 },
    { mes: '2026-10', etiqueta: 'oct', etiqueta_larga: 'octubre de 2026', ingresos: 3_000_000, gastos: 1_000_000, balance: 2_000_000 },
  ],
}

describe('IngresosGastos', () => {
  beforeEach(() => {
    api.ingresosGastos = vi.fn().mockResolvedValue(DATOS)
    api.informeNoSeCuenta = vi.fn().mockResolvedValue({
      cantidad: 1, truncado: false, grupos: [{ nombre: 'Traslado entre tus cuentas', cantidad: 1, monto: 400000 }],
      movimientos: [{ id: 'm', fecha: '2026-10-05T12:00:00', descripcion: 'Enviaste a Ana', monto: 400000, motivo: 'Traslado entre tus cuentas' }],
    })
  })

  it('muestra ingresos, gastos, balance con signo, tasa, gráfico accesible y la nota', async () => {
    render(<MemoryRouter><IngresosGastos params={{ periodo: 'este_mes' }} fmt={fmt} /></MemoryRouter>)
    expect((await screen.findAllByText('Ingresos')).length).toBeGreaterThan(0)
    expect(screen.getByText('$3.000.000')).toBeInTheDocument()
    expect(screen.getByText('+$2.000.000')).toBeInTheDocument()
    expect(screen.getByText('66,7 %')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /octubre de 2026, ingresos \$3\.000\.000, gastos \$1\.000\.000/ })).toBeInTheDocument()
    expect(screen.getByText(/No incluye traslados entre tus cuentas ni pagos de tarjeta/)).toBeInTheDocument()
  })

  it('«Ver lo que no se cuenta» lista los movimientos neutrales', async () => {
    render(<MemoryRouter><IngresosGastos params={{ periodo: 'este_mes' }} fmt={fmt} /></MemoryRouter>)
    await userEvent.click(await screen.findByRole('button', { name: /Ver lo que no se cuenta/ }))
    expect(await screen.findByText('Enviaste a Ana')).toBeInTheDocument()
    await waitFor(() => expect(api.informeNoSeCuenta).toHaveBeenCalled())
  })

  it('sin datos: estado vacío amable', async () => {
    api.ingresosGastos.mockResolvedValue({ ...DATOS, hay_datos: false })
    render(<MemoryRouter><IngresosGastos params={{}} fmt={fmt} /></MemoryRouter>)
    expect(await screen.findByText(/Cuando registres ingresos y gastos/)).toBeInTheDocument()
  })

  it('sin ingresos no hay tasa de ahorro', async () => {
    api.ingresosGastos.mockResolvedValue({ ...DATOS, ingresos: 0, tasa_ahorro: null, balance: -1000, gastos: 1000 })
    render(<MemoryRouter><IngresosGastos params={{}} fmt={fmt} /></MemoryRouter>)
    expect(await screen.findByText('Sin ingresos en el periodo')).toBeInTheDocument()
  })
})
