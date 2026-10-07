// El encabezado de Cuentas (saldo total / deudas) se refresca cuando el contexto recarga las cuentas.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const estado = vi.hoisted(() => ({ cuentas: [] }))
const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: estado.cuentas, cargando: false, error: '', recargar: vi.fn() }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Cuentas from '../screens/Cuentas'

const montar = () => (
  <ThemeProvider>
    <DialogosProvider>
      <MemoryRouter>
        <Cuentas />
      </MemoryRouter>
    </DialogosProvider>
  </ThemeProvider>
)

const cuenta = (id, tipo = 'ahorro', saldo = 1000) => ({ id, nombre: `Cuenta ${id}`, tipo, saldo, moneda: 'COP', icono: '🏦' })

beforeEach(() => {
  vi.clearAllMocks()
  estado.cuentas = [cuenta('a')]
  Object.assign(api, {
    resumenCuentas: vi
      .fn()
      .mockResolvedValueOnce({ total_cop: 1250000, deudas_tarjeta_cop: 0, ultimo_movimiento: null })
      .mockResolvedValue({ total_cop: 450000, deudas_tarjeta_cop: 800000, ultimo_movimiento: null }),
  })
})

describe('Cuentas: resumen del encabezado', () => {
  it('se vuelve a pedir cuando cambian las cuentas del contexto (p. ej. al crear una tarjeta)', async () => {
    const { rerender } = render(montar())
    await waitFor(() => expect(api.resumenCuentas).toHaveBeenCalledTimes(1))
    expect(await screen.findByLabelText('Saldo actual total')).toHaveTextContent('1.250.000')

    estado.cuentas = [cuenta('a'), cuenta('t', 'credito', -800000)]
    rerender(montar())
    await waitFor(() => expect(api.resumenCuentas).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.getByLabelText('Saldo actual total')).toHaveTextContent('450.000'))
  })
})
