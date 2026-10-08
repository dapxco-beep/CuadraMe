import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({ usuario: { id: 'u1', email: 'l@test.com', nombre: 'Laura Gómez' } }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ iconoDe: () => '💳' }),
}))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import Inicio from '../screens/Inicio'
import Patrimonio from '../screens/Patrimonio'
import BottomNav, { ITEMS_MAS } from '../components/BottomNav'
import { Monto, CargandoMarca, SelloCuadre } from '../brand/Marca'
import { dibujarTarjeta } from '../lib/wrappedImagen'
import { MASCARA } from '../lib/BloqueoContext'

function montar(ui, ruta = '/') {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter initialEntries={[ruta]}>{ui}</MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

const bolsillo = (disponible_real) => ({
  saldo_total: 1_000_000, recurrentes_pendientes_mes: 0, aportes_comprometidos_mes: 0,
  disponible_real, disponible_real_por_dia: 10_000,
})

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    cuentas: vi.fn().mockResolvedValue([{ id: 'c1', nombre: 'Bancolombia', saldo: 1_000_000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]),
    movimientos: vi.fn().mockResolvedValue([]),
    reporteMensual: vi.fn().mockResolvedValue({ salud: { score: 80, tips: ['ok'] }, top_categorias: [] }),
    disponibleHoy: vi.fn().mockResolvedValue({ categorias: [] }),
    enMiBolsillo: vi.fn().mockResolvedValue(bolsillo(400_000)),
    gmailEstado: vi.fn().mockResolvedValue({ conectado: true }),
    saludFinanciera: vi.fn().mockResolvedValue(null),
    patrimonio: vi.fn(),
  })
})

describe('Inicio — héroe de cuadre', () => {
  it('dice que las cuentas cuadran cuando alcanza para lo comprometido', async () => {
    montar(<Inicio />)
    expect(await screen.findByText('Tus cuentas cuadran')).toBeInTheDocument()
  })

  it('muestra la diferencia por cuadrar cuando no alcanza', async () => {
    api.enMiBolsillo.mockResolvedValue(bolsillo(-250_000))
    montar(<Inicio />)
    expect(await screen.findByText(/Te faltan .*250\.000.* por cuadrar/)).toBeInTheDocument()
    expect(screen.queryByText('Tus cuentas cuadran')).toBeNull()
  })

  it('con el estado vacío de movimientos invita a registrar el primero', async () => {
    montar(<Inicio />)
    expect(await screen.findByText('Aún no tienes movimientos registrados')).toBeInTheDocument()
  })
})

describe('Barra de navegación', () => {
  it('deja Movimientos y Presupuesto a un toque, y el resto en "Más"', async () => {
    montar(<BottomNav />)
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    expect(within(nav).getByRole('link', { name: 'Inicio' })).toHaveAttribute('href', '/')
    expect(within(nav).getByRole('link', { name: 'Movimientos' })).toHaveAttribute('href', '/movimientos')
    expect(within(nav).getByRole('link', { name: 'Presupuesto' })).toHaveAttribute('href', '/presupuesto')
    expect(within(nav).getByRole('link', { name: 'Agregar movimiento' })).toHaveAttribute('href', '/agregar')
    expect(screen.queryByRole('dialog')).toBeNull()

    await userEvent.click(within(nav).getByRole('button', { name: 'Más' }))
    const hoja = await screen.findByRole('dialog', { name: 'Más opciones' })
    for (const { label, to } of ITEMS_MAS) {
      expect(within(hoja).getByRole('link', { name: label })).toHaveAttribute('href', to)
    }
    expect(within(hoja).getByRole('link', { name: 'Patrimonio' })).toBeInTheDocument()
    expect(within(hoja).getByRole('link', { name: 'Perfil' })).toBeInTheDocument()
  })

  it('la hoja se cierra con Escape', async () => {
    montar(<BottomNav />)
    await userEvent.click(screen.getByRole('button', { name: 'Más' }))
    await screen.findByRole('dialog')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('"Más" se ve activo en pantallas que viven dentro de él', () => {
    montar(<BottomNav />, '/patrimonio')
    expect(screen.getByRole('button', { name: 'Más' }).className).toMatch(/text-accent/)
  })
})

describe('Patrimonio — aviso de cuentas de inversión', () => {
  it('avisa que las cuentas de inversión ya se cuentan', async () => {
    api.patrimonio.mockResolvedValue({
      patrimonio_neto: 0, total_activos: 0, total_cuentas: 0, total_deudas: 0, variacion_mes_anterior: null,
      distribucion: [], historial: [], pasivos: [], activos: [],
    })
    montar(<Patrimonio />)
    expect(await screen.findByText(/cuentas de tipo inversión ya se cuentan/)).toBeInTheDocument()
  })
})

describe('Imagen compartible del resumen', () => {
  const datos = {
    mes: '2026-09', gasto_total: 1_234_567, num_movimientos: 12, ingresos: 3_000_000, ahorro: 500_000,
    tasa_ahorro: 17, mejor_racha: 4, categoria_top: { categoria: 'Mercado', monto: 400_000 },
    variacion_gasto_pct: -10, gasto_mes_anterior: 1_400_000,
  }
  function ctxFalso() {
    const textos = []
    const ctx = new Proxy(
      { fillText: (t) => textos.push(String(t)), measureText: () => ({ width: 100 }), createLinearGradient: () => ({ addColorStop() {} }) },
      { get: (o, p) => (p in o ? o[p] : () => {}), set: () => true }
    )
    return { ctx, textos }
  }

  it('enmascara los montos cuando se le pasa el formateador de "ocultar saldos"', () => {
    const { ctx, textos } = ctxFalso()
    dibujarTarjeta(ctx, datos, () => MASCARA)
    const todo = textos.join(' ')
    expect(todo).toContain(MASCARA)
    expect(todo).not.toMatch(/1\.234\.567|500\.000|400\.000/)
    expect(todo).toContain('CuadraMe')
  })

  it('por defecto muestra los montos reales y la firma de marca', () => {
    const { ctx, textos } = ctxFalso()
    dibujarTarjeta(ctx, datos)
    expect(textos.join(' ')).toMatch(/1\.234\.567/)
    expect(textos).toContain('Cuadra tus cuentas, simple y al día')
  })
})

describe('Componentes de marca', () => {
  it('Monto separa el símbolo pero conserva el texto completo para lectores de pantalla', () => {
    render(<Monto texto="$ 1.750.000" />)
    expect(screen.getByText('$ 1.750.000')).toHaveClass('sr-only')
  })

  it('Monto no rompe un monto enmascarado', () => {
    render(<Monto texto={MASCARA} />)
    expect(screen.getByText(MASCARA)).toBeInTheDocument()
  })

  it('el loader es un estado accesible y el sello está oculto a lectores', () => {
    const { container } = render(
      <>
        <CargandoMarca texto="Cargando tus cuentas" />
        <SelloCuadre />
      </>
    )
    expect(screen.getByRole('status')).toHaveTextContent('Cargando tus cuentas')
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull()
  })
})
