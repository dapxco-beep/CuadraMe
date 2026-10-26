import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [
  { id: 'c1', nombre: 'Bancolombia', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
  { id: 'c2', nombre: 'Nequi', saldo: 200000, moneda: 'COP', tipo: 'ahorro', icono: '💜' },
  { id: 'c3', nombre: 'Wise', saldo: 50, moneda: 'USD', tipo: 'ahorro', icono: '💵' },
]
const MOVS = [
  { id: 'm1', cuenta_id: 'c1', fecha: '2026-10-02T12:00:00', descripcion: 'Éxito', categoria: 'Mercado', tipo: 'expense', monto: 80000, fuente: 'manual', notas: '' },
  { id: 'm2', cuenta_id: 'c1', fecha: '2026-10-01T12:00:00', descripcion: 'Nómina', categoria: 'Ingresos', tipo: 'income', monto: 3000000, fuente: 'manual', notas: '' },
  { id: 'm3', cuenta_id: 'c3', fecha: '2026-10-01T10:00:00', descripcion: 'Spotify', categoria: 'Suscripciones', tipo: 'expense', monto: 10, fuente: 'manual', notas: '' },
  { id: 'm4', cuenta_id: 'c1', fecha: '2026-09-30T10:00:00', descripcion: 'Transferencia a Nequi', categoria: 'Transferencia', tipo: 'transfer', monto: 50000, fuente: 'transferencia_interna', notas: 'TRF:g:out' },
]

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({
    usuario: { id: 'u1', email: 'laura@test.com', nombre: 'Laura Gómez' },
    login: vi.fn(), registro: vi.fn(), loginConGoogle: vi.fn(), logout: vi.fn(),
    recuperarPassword: api.recuperarPassword, cambiarPassword: vi.fn(),
  }),
}))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({
    categorias: [], nombres: ['Mercado', 'Transporte', 'Ingresos'], cargando: false, recargar: vi.fn(),
    iconoDe: (n) => ({ Mercado: '🛒', Transporte: '🚌' })[n] || '💳',
  }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import Login from '../screens/Login'
import Inicio from '../screens/Inicio'
import Movimientos from '../screens/Movimientos'
import Agregar from '../screens/Agregar'
import DetalleMovimiento from '../screens/DetalleMovimiento'
import Perfil from '../screens/Perfil'
import Cuentas from '../screens/Cuentas'
import CrearCuenta from '../screens/CrearCuenta'
import { ThemeProvider } from '../lib/ThemeContext'

function montar(ui, ruta = '/') {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter initialEntries={[ruta]}>{ui}</MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    cuentas: vi.fn().mockResolvedValue(CUENTAS),
    movimientos: vi.fn().mockResolvedValue(MOVS),
    movimiento: vi.fn((id) => Promise.resolve(MOVS.find((m) => m.id === id))),
    editarMovimiento: vi.fn((id, d) => Promise.resolve({ ...MOVS.find((m) => m.id === id), ...d })),
    eliminarMovimiento: vi.fn().mockResolvedValue({ ok: true }),
    crearMovimiento: vi.fn().mockResolvedValue({}),
    crearTransferencia: vi.fn().mockResolvedValue({ ok: true }),
    clasificar: vi.fn().mockResolvedValue({ categoria: 'Otros' }),
    reporteMensual: vi.fn().mockResolvedValue({
      salud: { score: 80, tips: ['Vas bien'] },
      top_categorias: [{ categoria: 'Mercado', monto: 80000 }],
    }),
    disponibleHoy: vi.fn().mockResolvedValue({ categorias: [], disponible_total_hoy: 0, disponible_total_mes: 0, dias_restantes_mes: 10 }),
    enMiBolsillo: vi.fn().mockResolvedValue({
      saldo_total: 1750000, recurrentes_pendientes_mes: 0, aportes_comprometidos_mes: 0,
      disponible_real: 1750000, disponible_real_por_dia: 100000,
    }),
    gmailEstado: vi.fn().mockResolvedValue({ conectado: true }),
    apiKey: vi.fn().mockResolvedValue({ api_key: 'k' }),
    confianzaAutoimport: vi.fn().mockResolvedValue({ confianza_autoimport: 0.75 }),
    eliminarMiCuenta: vi.fn().mockResolvedValue({ ok: true }),
    crearCuenta: vi.fn().mockResolvedValue({}),
    recuperarPassword: vi.fn().mockResolvedValue(),
    misInvitacionesPendientes: vi.fn().mockResolvedValue([]),
    invitacionesDeCuenta: vi.fn().mockResolvedValue([]),
  })
})

describe('Login', () => {
  it('muestra olvidé mi contraseña y avisa si falta el correo', async () => {
    montar(<Login />)
    await userEvent.click(screen.getByText('¿Olvidaste tu contraseña?'))
    expect(await screen.findByRole('alert')).toHaveTextContent(/Escribe tu correo/)
    await userEvent.type(screen.getByLabelText('Correo'), 'laura@test.com')
    await userEvent.click(screen.getByText('¿Olvidaste tu contraseña?'))
    await waitFor(() => expect(api.recuperarPassword).toHaveBeenCalledWith('laura@test.com'))
    expect(await screen.findByRole('status')).toHaveTextContent(/Si ese correo tiene cuenta/)
  })

  it('el registro exige aceptar los términos', async () => {
    montar(<Login />)
    await userEvent.click(screen.getByText(/Regístrate/))
    expect(screen.getByRole('button', { name: 'Crear cuenta' })).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox'))
    expect(screen.getByRole('button', { name: 'Crear cuenta' })).toBeEnabled()
  })
})

describe('Inicio', () => {
  it('saluda con el nombre del usuario y no con uno fijo', async () => {
    montar(<Inicio />)
    expect(await screen.findByText('Hola, Laura')).toBeInTheDocument()
    expect(screen.queryByText(/Daniel/)).toBeNull()
  })

  it('muestra el aviso de error y permite reintentar', async () => {
    api.cuentas.mockRejectedValueOnce(new Error('Sin conexión'))
    montar(<Inicio />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión')
    await userEvent.click(screen.getByText('Reintentar'))
    await waitFor(() => expect(api.cuentas).toHaveBeenCalledTimes(2))
  })
})

describe('Movimientos', () => {
  it('lista, muestra iconos por categoría y trata la transferencia sin signo', async () => {
    montar(<Movimientos />)
    expect(await screen.findByText('Éxito')).toBeInTheDocument()
    expect(screen.getByText('Nómina')).toBeInTheDocument()
    expect(screen.getByText('Transferencia a Nequi')).toBeInTheDocument()
    // el movimiento en USD se muestra en dólares, no en pesos
    expect(screen.getByText(/US\$|USD/)).toBeInTheDocument()
  })

  it('tiene un acceso al detalle de los gastos (En qué gasto)', async () => {
    montar(<Movimientos />)
    const enlace = await screen.findByTestId('ver-detalle-gastos')
    expect(enlace).toHaveAttribute('href', '/informe')
    expect(enlace).toHaveTextContent('Ver detalle de tus gastos')
  })

  it('ofrece cargar más cuando la página viene llena', async () => {
    api.movimientos.mockResolvedValueOnce(Array.from({ length: 200 }, (_, i) => ({ ...MOVS[0], id: `x${i}` })))
    montar(<Movimientos />)
    expect(await screen.findByText('Cargar movimientos anteriores')).toBeInTheDocument()
    api.movimientos.mockResolvedValueOnce([])
    await userEvent.click(screen.getByText('Cargar movimientos anteriores'))
    await waitFor(() => expect(api.movimientos).toHaveBeenLastCalledWith(200, 200))
  })
})

describe('Agregar', () => {
  it('guarda un gasto normal', async () => {
    montar(<Agregar />)
    await userEvent.type(screen.getByPlaceholderText('0'), '25000')
    await userEvent.type(screen.getByPlaceholderText(/¿En qué fue/), 'Uber')
    await userEvent.click(screen.getByText('Guardar movimiento'))
    await waitFor(() =>
      expect(api.crearMovimiento).toHaveBeenCalledWith(
        expect.objectContaining({ cuenta_id: 'c1', monto: 25000, tipo: 'expense', descripcion: 'Uber' })
      )
    )
  })

  it('hace una transferencia entre cuentas', async () => {
    montar(<Agregar />)
    await userEvent.click(screen.getByRole('button', { name: 'Transferir' }))
    expect(screen.queryByPlaceholderText(/¿En qué fue/)).toBeNull()
    await userEvent.type(screen.getByPlaceholderText('0'), '40000')
    await userEvent.click(screen.getByText('Pasar la plata'))
    await waitFor(() =>
      expect(api.crearTransferencia).toHaveBeenCalledWith(
        expect.objectContaining({ cuenta_origen_id: 'c1', cuenta_destino_id: 'c2', monto: 40000 })
      )
    )
  })

  it('valida monto y descripción', async () => {
    montar(<Agregar />)
    await userEvent.click(screen.getByText('Guardar movimiento'))
    expect(await screen.findByText(/Escribe cuánto fue/)).toBeInTheDocument()
    expect(api.crearMovimiento).not.toHaveBeenCalled()
  })
})

describe('DetalleMovimiento', () => {
  function detalle(id) {
    return montar(
      <Routes>
        <Route path="/movimientos/:id" element={<DetalleMovimiento />} />
        <Route path="/movimientos" element={<p>lista</p>} />
      </Routes>,
      `/movimientos/${id}`
    )
  }

  it('edita monto y descripción', async () => {
    detalle('m1')
    await userEvent.click(await screen.findByLabelText('Editar movimiento'))
    const monto = screen.getByLabelText('Monto')
    await userEvent.clear(monto)
    await userEvent.type(monto, '95000')
    await userEvent.click(screen.getByText('Guardar cambios'))
    await waitFor(() =>
      expect(api.editarMovimiento).toHaveBeenCalledWith('m1', expect.objectContaining({ monto: 95000 }))
    )
  })

  it('un movimiento mal registrado se pasa de gasto a ingreso con un toque (pide confirmar)', async () => {
    detalle('m1')
    await userEvent.click(await screen.findByTestId('cambiar-tipo-rapido'))
    expect(api.editarMovimiento).not.toHaveBeenCalled()
    await userEvent.click(await screen.findByRole('button', { name: 'Cambiar' }))
    await waitFor(() => expect(api.editarMovimiento).toHaveBeenCalledWith('m1', expect.objectContaining({ tipo: 'income' })))
  })

  it('pide confirmación antes de eliminar', async () => {
    detalle('m1')
    await userEvent.click(await screen.findByText('Eliminar movimiento'))
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()
    expect(api.eliminarMovimiento).not.toHaveBeenCalled()
    await userEvent.click(screen.getByText('Eliminar', { selector: 'button.bg-danger' }))
    await waitFor(() => expect(api.eliminarMovimiento).toHaveBeenCalledWith('m1'))
  })

  it('las transferencias no se pueden editar', async () => {
    detalle('m4')
    await screen.findByText('Detalle del movimiento')
    expect(screen.queryByLabelText('Editar movimiento')).toBeNull()
  })

  it('movimiento inexistente muestra un mensaje, no una pantalla vacía', async () => {
    api.movimiento.mockRejectedValueOnce(new Error('404'))
    detalle('nope')
    expect(await screen.findByText(/No encontramos este movimiento/)).toBeInTheDocument()
  })
})

describe('Perfil', () => {
  it('eliminar cuenta exige escribir ELIMINAR (no basta un toque)', async () => {
    montar(<Perfil />)
    await userEvent.click(await screen.findByText('Borrar mi cuenta y todos mis datos'))
    const borrar = await screen.findByRole('button', { name: 'Borrar todo' })
    expect(borrar).toBeDisabled()
    expect(api.eliminarMiCuenta).not.toHaveBeenCalled()
    await userEvent.type(screen.getByLabelText(/escribe ELIMINAR/), 'ELIMINAR')
    await userEvent.click(borrar)
    await waitFor(() => expect(api.eliminarMiCuenta).toHaveBeenCalledWith('ELIMINAR'))
  })
})

describe('Cuentas y CrearCuenta', () => {
  it('crear cuenta permite elegir moneda', async () => {
    montar(<CrearCuenta onCreada={vi.fn()} />)
    await userEvent.click(screen.getByText(/Empezar/))
    await userEvent.click(screen.getByRole('button', { name: 'USD' }))
    await userEvent.type(screen.getByPlaceholderText(/Nombre de la cuenta/), 'Wise')
    await userEvent.click(screen.getByText('Crear mi cuenta'))
    await waitFor(() =>
      expect(api.crearCuenta).toHaveBeenCalledWith(expect.objectContaining({ nombre: 'Wise', moneda: 'USD' }))
    )
  })

  it('lista las cuentas con su moneda', async () => {
    montar(<Cuentas />)
    expect(await screen.findByText('Wise')).toBeInTheDocument()
  })
})
