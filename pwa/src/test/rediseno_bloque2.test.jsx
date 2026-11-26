// Rediseño UX, bloque 2 (2026-11-26): Presupuesto, Metas y Cuentas. Cifras alineadas, errores honestos, un solo sitio para cada dato.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => ({ usuario: { id: 'u1', email: 'a@test.com', nombre: 'Ana' } }) }))
vi.mock('../lib/CuentasContext', () => ({ useCuentas: () => ({ cuentas: [], cargando: false, error: '', recargar: vi.fn() }) }))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ categorias: [], nombres: ['Comida'], cargando: false, recargar: vi.fn(), iconoDe: () => '🍔' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Presupuesto from '../screens/Presupuesto'
import Metas from '../screens/Metas'
import TarjetaCuenta from '../components/TarjetaCuenta'

const montar = (ui) => render(
  <ThemeProvider><DialogosProvider><MemoryRouter>{ui}</MemoryRouter></DialogosProvider></ThemeProvider>
)

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    presupuestos: vi.fn().mockResolvedValue([{ id: 'p1', categoria: 'Comida', limite: 400000, gastado: 100000, periodo: 'monthly', alerta_pct: 80, sobre_ajuste: 0, activo: true }]),
    reporteMensual: vi.fn().mockResolvedValue({ top_categorias: [{ categoria: 'Comida', monto: 100000 }] }),
    tendencias: vi.fn().mockResolvedValue({ meses: [], proyeccion: null }),
    flujoCajaFuturo: vi.fn().mockResolvedValue({ saldo_actual: 0, meses: [] }),
    proyeccionPresupuestos: vi.fn().mockResolvedValue(null),
    metas: vi.fn().mockResolvedValue([]),
    metasSugerencias: vi.fn().mockResolvedValue({ metas: {} }),
    consejos: vi.fn().mockResolvedValue({ consejos: [] }),
  })
})

describe('Presupuesto: un fallo de carga no se disfraza de «aún no tienes presupuestos»', () => {
  it('si la API falla dice que no pudo cargar y ofrece Reintentar', async () => {
    api.presupuestos.mockRejectedValueOnce(new Error('Sin conexión. Revisa tu internet.'))
    montar(<Presupuesto />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión')
    expect(screen.queryByText(/Aún no tienes presupuestos/)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    await waitFor(() => expect(screen.getByTestId('gastado-limite')).toBeInTheDocument())
  })
  it('la tarjeta muestra siempre Llevas, Límite y Te queda, y quitar solo aparece en el detalle', async () => {
    montar(<Presupuesto />)
    const cifras = await screen.findByTestId('gastado-limite')
    expect(within(cifras).getByText('Llevas')).toBeInTheDocument()
    expect(within(cifras).getByText('Límite')).toBeInTheDocument()
    expect(within(cifras).getByText('Te queda')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Quitar el presupuesto de Comida/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /Ver detalle/ }))
    expect(screen.getByRole('button', { name: /Quitar el presupuesto de Comida/ })).toBeInTheDocument()
  })
})

describe('Metas: progreso, acumulado, objetivo y lo que falta, sin repetir', () => {
  const META = { id: 'm1', nombre: 'Viaje', monto_objetivo: 3000000, monto_actual: 600000, progreso_pct: 20, completada: false, dias_restantes: 30, fecha_objetivo: '2027-01-15T00:00:00' }
  it('la tarjeta lleva Llevas / Objetivo / Te falta y los días que quedan', async () => {
    api.metas.mockResolvedValue([META])
    montar(<Metas />)
    const t = await screen.findByTestId('meta-m1')
    expect(within(t).getByText('Llevas')).toBeInTheDocument()
    expect(within(t).getByText('Objetivo')).toBeInTheDocument()
    expect(within(t).getByText('Te falta')).toBeInTheDocument()
    expect(within(t).getByText(/faltan 30 días/)).toBeInTheDocument()
    expect(within(t).getByText('20 %')).toBeInTheDocument()
  })
  it('una meta completada lo dice una sola vez y no ofrece aportar', async () => {
    api.metas.mockResolvedValue([{ ...META, monto_actual: 3000000, progreso_pct: 100, completada: true, dias_restantes: null }])
    montar(<Metas />)
    const t = await screen.findByTestId('meta-m1')
    expect(within(t).getAllByText('¡Meta completada!')).toHaveLength(1)
    expect(within(t).queryByRole('button', { name: 'Aportar ahora' })).toBeNull()
  })
  it('si falla la carga, Reintentar vuelve a pedirlas', async () => {
    api.metas.mockRejectedValueOnce(new Error('Sin conexión.')).mockResolvedValue([META])
    montar(<Metas />)
    await userEvent.click(await screen.findByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByTestId('meta-m1')).toBeInTheDocument()
  })
})

describe('TarjetaCuenta: el tipo de cuenta vive dentro de la tarjeta', () => {
  const cuenta = { id: 'c1', nombre: 'Bancolombia Ahorros', saldo: 100000, moneda: 'COP', tipo: 'ahorro' }
  it('muestra la etiqueta de tipo bajo el nombre', () => {
    montar(<TarjetaCuenta cuenta={cuenta} etiqueta="Cuenta de ahorros" />)
    expect(screen.getByText('Cuenta de ahorros')).toBeInTheDocument()
  })
  it('no repite la etiqueta cuando es igual al nombre', () => {
    montar(<TarjetaCuenta cuenta={{ ...cuenta, nombre: 'Efectivo' }} etiqueta="Efectivo" />)
    expect(screen.getAllByText('Efectivo')).toHaveLength(1)
  })
})
