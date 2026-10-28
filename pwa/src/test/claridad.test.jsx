// Claridad de textos y retroalimentación: guardar avisa con un toast claro (con «Deshacer» donde se puede),
// los errores dicen qué hacer y los nombres de pantalla no usan jerga.
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const CUENTAS = [
  { id: 'c1', nombre: 'Bancolombia', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
  { id: 'c2', nombre: 'Visa', saldo: -240000, moneda: 'COP', tipo: 'credito', icono: '💳', cupo_total: 3000000 },
]
const recargar = vi.hoisted(() => vi.fn())
const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({ usuario: { id: 'u1', email: 'laura@test.com', nombre: 'Laura Gómez' } }),
}))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({
    categorias: [], nombres: ['Comida', 'Transporte', 'Ingresos', 'Transferencias'], cargando: false, recargar: vi.fn(),
    iconoDe: () => '💳',
  }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Agregar from '../screens/Agregar'
import Presupuesto from '../screens/Presupuesto'
import Recurrentes from '../screens/Recurrentes'
import Metas from '../screens/Metas'

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
    crearMovimiento: vi.fn().mockResolvedValue({ id: 'nuevo1' }),
    eliminarMovimiento: vi.fn().mockResolvedValue({ ok: true }),
    crearTransferencia: vi.fn().mockResolvedValue({ ok: true }),
    clasificar: vi.fn().mockResolvedValue({ categoria: 'Comida' }),
    movimientos: vi.fn().mockResolvedValue([]),
    frecuentes: vi.fn().mockResolvedValue([]),
    presupuestos: vi.fn().mockResolvedValue([{ id: 'p1', categoria: 'Comida', limite: 400000, periodo: 'monthly', alerta_pct: 80, sobre_ajuste: 0, activo: true }]),
    reporteMensual: vi.fn().mockResolvedValue({ top_categorias: [{ categoria: 'Comida', monto: 100000 }] }),
    tendencias: vi.fn().mockResolvedValue({ meses: [], proyeccion: null }),
    flujoCajaFuturo: vi.fn().mockResolvedValue({ saldo_actual: 0, meses: [] }),
    proyeccionPresupuestos: vi.fn().mockResolvedValue(null),
    eliminarPresupuesto: vi.fn().mockResolvedValue({ ok: true }),
    crearPresupuesto: vi.fn().mockResolvedValue({ id: 'p2' }),
    recurrentes: vi.fn().mockResolvedValue([]),
    sugerenciasRecurrentes: vi.fn().mockResolvedValue([]),
    crearRecurrente: vi.fn().mockResolvedValue({ id: 'r1' }),
    metas: vi.fn().mockResolvedValue([]),
    crearMeta: vi.fn().mockResolvedValue({ id: 'g1' }),
  })
})

describe('Agregar: retroalimentación', () => {
  it('al guardar un gasto avisa con «Deshacer», y Deshacer lo quita', async () => {
    montar(<Agregar />)
    await userEvent.type(screen.getByPlaceholderText('0'), '32000')
    await userEvent.type(screen.getByPlaceholderText(/¿En qué fue/), 'Rappi cena')
    await userEvent.click(screen.getByText('Guardar movimiento'))
    expect(await screen.findByText(/Guardado: Rappi cena/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }))
    await waitFor(() => expect(api.eliminarMovimiento).toHaveBeenCalledWith('nuevo1'))
  })

  it('los errores dicen qué hacer: sin monto pide escribir cuánto fue', async () => {
    montar(<Agregar />)
    await userEvent.click(screen.getByText('Guardar movimiento'))
    expect(await screen.findByRole('alert')).toHaveTextContent(/Escribe cuánto fue/)
  })

  it('pagar una tarjeta se llama «Pagar la tarjeta» y avisa que no es un gasto nuevo', async () => {
    montar(<Agregar />)
    await userEvent.click(screen.getByRole('button', { name: 'Pasar plata' }))
    await userEvent.type(screen.getByPlaceholderText('0'), '100000')
    await userEvent.click(screen.getByRole('button', { name: 'Pagar la tarjeta' }))
    expect(await screen.findByText(/pagaste .*100\.000.* a Visa\. No cuenta como gasto nuevo/)).toBeInTheDocument()
  })
})

describe('Presupuesto', () => {
  it('quitar un presupuesto avisa con «Deshacer» y Deshacer lo vuelve a crear', async () => {
    montar(<Presupuesto />)
    await userEvent.click(await screen.findByRole('button', { name: 'Quitar el presupuesto de Comida' }))
    await waitFor(() => expect(api.eliminarPresupuesto).toHaveBeenCalledWith('p1'))
    await userEvent.click(await screen.findByRole('button', { name: 'Deshacer' }))
    await waitFor(() =>
      expect(api.crearPresupuesto).toHaveBeenCalledWith({ categoria: 'Comida', limite: 400000, periodo: 'monthly' })
    )
  })

  it('sin presupuestos explica qué es uno y ofrece crear el primero', async () => {
    api.presupuestos.mockResolvedValue([])
    montar(<Presupuesto />)
    expect(await screen.findByText(/lo máximo que quieres gastar en algo/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Crear mi primer presupuesto' })).toBeInTheDocument()
  })
})

describe('Pagos fijos (antes «Recurrentes»)', () => {
  it('usa «Pagos fijos», lo explica y el vacío trae un botón para agregar', async () => {
    montar(<Recurrentes />)
    expect(await screen.findByRole('heading', { name: 'Pagos fijos' })).toBeInTheDocument()
    expect(screen.getByText(/Lo que pagas o recibes cada mes/)).toBeInTheDocument()
    await userEvent.click((await screen.findAllByRole('button', { name: 'Agregar un pago fijo' }))[0])
    expect(await screen.findByLabelText('¿Qué es?')).toBeInTheDocument()
  })

  it('crear un pago fijo avisa con un mensaje claro', async () => {
    montar(<Recurrentes />)
    await userEvent.click((await screen.findAllByRole('button', { name: 'Agregar un pago fijo' }))[0])
    await userEvent.type(await screen.findByLabelText('¿Qué es?'), 'Netflix')
    await userEvent.type(screen.getByLabelText('¿De cuánto es?'), '45000')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar pago fijo' }))
    expect(await screen.findByText(/«Netflix» quedó en tus pagos fijos/)).toBeInTheDocument()
  })
})

describe('Metas', () => {
  it('el estado vacío explica qué es una meta y trae el botón para crear la primera', async () => {
    montar(<Metas />)
    expect(await screen.findByText(/Una meta es algo que quieres comprar o lograr/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Crear mi primera meta' }))
    expect(await screen.findByLabelText('¿Cuánta plata necesitas en total?')).toBeInTheDocument()
  })
})
