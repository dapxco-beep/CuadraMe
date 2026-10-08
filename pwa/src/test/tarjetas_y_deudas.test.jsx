import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const TARJETA = {
  id: 't1', nombre: 'Visa Bancolombia', saldo: -1700000, moneda: 'COP', tipo: 'credito', icono: '💳',
  cupo_total: 2000000, dia_corte: 10, dia_pago: 25, tasa_ea: 28.5,
  tarjeta: {
    cupo_usado: 1700000, cupo_disponible: 300000, utilizacion_pct: 85, nivel_utilizacion: 'critico',
    proximo_corte: '2026-10-10', proximo_pago: '2026-10-25', dias_para_corte: 7, dias_para_pago: 22,
    pago_minimo_estimado: 123000, interes_estimado: 36000,
  },
}
const TARJETA_SIN_DATOS = {
  id: 't2', nombre: 'Nu', saldo: 0, moneda: 'COP', tipo: 'credito', icono: '💳',
  cupo_total: null, dia_corte: null, dia_pago: null, tasa_ea: null,
  tarjeta: {
    cupo_usado: 0, cupo_disponible: null, utilizacion_pct: null, nivel_utilizacion: 'sin_cupo',
    proximo_corte: null, proximo_pago: null, dias_para_corte: null, dias_para_pago: null,
    pago_minimo_estimado: 0, interes_estimado: null,
  },
}
const CUENTAS = [
  { id: 'c1', nombre: 'Bancolombia', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: '🏦', tarjeta: null },
  TARJETA,
  TARJETA_SIN_DATOS,
]

const DEUDA = {
  id: 'd1', nombre: 'Préstamo', tipo: 'credito', entidad: 'Davivienda', saldo_inicial: 1000000, saldo_actual: 1000000,
  tasa_mensual: 2, tasa_ea: 26.8, cuota_mensual: 80000, interes_este_mes: 20000, abono_capital: 60000,
  cuotas_faltantes: 15, fecha_inicio: '2026-01-01T00:00:00', fecha_fin: null, dia_corte: null, dia_pago: 5,
  dias_para_pago: 3, dias_para_corte: null, cuenta_pago_id: null, notas: '', urgencia: 'critico', activa: true,
}
const metodo = (id, extra) => ({
  metodo: id, meses: 12, fecha_libre: '2027-10', intereses_totales: 100000, ahorro_intereses: 0, meses_ahorrados: 0,
  orden: [], saldo_por_mes: [1000000, 0], ...extra,
})
const ESTRATEGIA = {
  extra_mensual: 200000, deuda_total: 1000000, mejor: 'avalancha',
  sin_extra: metodo('sin_extra', { meses: 18, fecha_libre: '2028-04', intereses_totales: 400000 }),
  avalancha: metodo('avalancha', { meses: 6, fecha_libre: '2027-04', intereses_totales: 90000, ahorro_intereses: 310000, meses_ahorrados: 12 }),
  bola_de_nieve: metodo('bola_de_nieve', { meses: 7, fecha_libre: '2027-05', intereses_totales: 120000, ahorro_intereses: 280000, meses_ahorrados: 11 }),
}

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: api.recargarCuentas }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Cuentas from '../screens/Cuentas'
import Deudas from '../screens/Deudas'

function montar(ui) {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    recargarCuentas: vi.fn(),
    editarCuenta: vi.fn().mockResolvedValue({}),
    deudas: vi.fn().mockResolvedValue([DEUDA]),
    estrategiaDeudas: vi.fn().mockResolvedValue(ESTRATEGIA),
  })
})

describe('Tarjeta de crédito en Cuentas', () => {
  it('muestra utilización, alerta crítica, fechas y pago mínimo', async () => {
    montar(<Cuentas />)
    const barra = await screen.findByRole('progressbar', { name: 'Utilización del cupo' })
    expect(barra).toHaveAttribute('aria-valuenow', '85')
    expect(screen.getByText('85 %')).toBeInTheDocument()
    expect(screen.getByText(/más del 80%/)).toBeInTheDocument()
    expect(screen.getByText('10 oct')).toBeInTheDocument()
    expect(screen.getByText('25 oct')).toBeInTheDocument()
    expect(screen.getByText(/Pago mínimo estimado/)).toBeInTheDocument()
    expect(screen.getByText(/Paga el total antes del 25 oct/)).toBeInTheDocument()
  })

  it('una cuenta de ahorro no muestra panel de tarjeta y la tarjeta vacía invita a configurarla', async () => {
    montar(<Cuentas />)
    await screen.findByText('Bancolombia')
    expect(screen.getAllByTestId('panel-tarjeta')).toHaveLength(2)
    expect(screen.getByText('Configurar tarjeta')).toBeInTheDocument()
  })

  it('editar los datos de la tarjeta guarda cupo, días y tasa', async () => {
    montar(<Cuentas />)
    await userEvent.click(await screen.findByText('Editar datos de la tarjeta'))
    const cupo = screen.getByLabelText('Cupo total')
    await userEvent.clear(cupo)
    await userEvent.type(cupo, '3000000')
    await userEvent.clear(screen.getByLabelText('Día de pago'))
    await userEvent.type(screen.getByLabelText('Día de pago'), '28')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() =>
      expect(api.editarCuenta).toHaveBeenCalledWith(
        't1',
        { cupo_total: 3000000, dia_corte: 10, dia_pago: 28, tasa_ea: 28.5 }
      )
    )
    expect(api.recargarCuentas).toHaveBeenCalled()
  })

  it('rechaza días fuera de 1-31 sin llamar al backend', async () => {
    montar(<Cuentas />)
    await userEvent.click(await screen.findByText('Editar datos de la tarjeta'))
    await userEvent.clear(screen.getByLabelText('Día de corte'))
    await userEvent.type(screen.getByLabelText('Día de corte'), '45')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/entre 1 y 31/)
    expect(api.editarCuenta).not.toHaveBeenCalled()
  })
})

describe('Simulador de estrategia en Deudas', () => {
  it('simula con el extra ingresado y muestra fecha libre y ahorro de cada método', async () => {
    montar(<Deudas />)
    await userEvent.type(await screen.findByLabelText(/cuánto extra/i), '200000')
    await userEvent.click(screen.getByRole('button', { name: 'Simular' }))
    await waitFor(() => expect(api.estrategiaDeudas).toHaveBeenCalledWith(200000))
    expect(await screen.findByText('abril de 2027')).toBeInTheDocument()
    expect(screen.getByText('mayo de 2027')).toBeInTheDocument()
    expect(screen.getByText('Menos intereses')).toBeInTheDocument()
    expect(screen.getAllByText(/Ahorras/)).toHaveLength(2)
    expect(screen.getByRole('img', { name: /Comparación de intereses/ })).toBeInTheDocument()
  })

  it('no aparece si no hay deudas', async () => {
    api.deudas.mockResolvedValueOnce([])
    montar(<Deudas />)
    await screen.findByText('No tienes deudas registradas')
    expect(screen.queryByText(/Simular/)).toBeNull()
  })

  it('muestra el error del backend', async () => {
    api.estrategiaDeudas.mockRejectedValueOnce(new Error('Sin conexión'))
    montar(<Deudas />)
    await userEvent.click(await screen.findByRole('button', { name: 'Simular' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión')
  })
})
