// Carga rápida de Cuentas: el resumen sale a la vez que las cuentas (sin cascada) y el cuadre,
// que es lo más caro del servidor, solo se pide cuando alguien abre «Más de esta cuenta».
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const estado = vi.hoisted(() => ({ cuentas: [], cargando: false }))
const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: estado.cuentas, cargando: estado.cargando, error: '', recargar: vi.fn() }),
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
const cuenta = (id) => ({ id, nombre: `Cuenta ${id}`, tipo: 'efectivo', saldo: 1000, moneda: 'COP', icono: '💵' })

beforeEach(() => {
  vi.clearAllMocks()
  estado.cuentas = [cuenta('a')]
  estado.cargando = false
  Object.assign(api, {
    resumenCuentas: vi.fn().mockResolvedValue({ total_cop: 1000, deudas_tarjeta_cop: 0, ultimo_movimiento: null }),
    cuadreResumen: vi.fn().mockResolvedValue({ cuentas: [{ cuenta_id: 'a', estado: 'cuadra', texto: 'Cuadra a junio' }] }),
  })
})

describe('Cuentas: carga rápida', () => {
  it('no pide el cuadre al pintar; lo pide una sola vez al abrir «Más de esta cuenta»', async () => {
    render(montar())
    await waitFor(() => expect(api.resumenCuentas).toHaveBeenCalledTimes(1))
    expect(api.cuadreResumen).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Más de esta cuenta'))
    expect(await screen.findByTestId('linea-cuadre')).toHaveTextContent('Cuadra a junio')
    expect(api.cuadreResumen).toHaveBeenCalledTimes(1)
  })

  it('el resumen sale mientras las cuentas todavía cargan y no se repite al llegar', async () => {
    estado.cuentas = []
    estado.cargando = true
    const { rerender } = render(montar())
    await waitFor(() => expect(api.resumenCuentas).toHaveBeenCalledTimes(1))
    estado.cuentas = [cuenta('a')]
    estado.cargando = false
    rerender(montar())
    await screen.findByLabelText('Ver detalle de Cuenta a')
    expect(api.resumenCuentas).toHaveBeenCalledTimes(1)
  })
})
