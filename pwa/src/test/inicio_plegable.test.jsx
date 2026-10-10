// Inicio simplificado: un bloque protagonista, dos acciones y el resto en secciones
// plegables que recuerdan su estado; mini gráfica de tendencia accesible.
import { beforeEach, describe, expect, it, vi } from 'vitest'
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
import SeccionPlegable from '../components/SeccionPlegable'

function montar(ui = <Inicio />) {
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
  localStorage.clear()
  localStorage.setItem('cuadrame:modo-completo:u1', '1') // el Inicio con todas las secciones (modo completo)
  Object.assign(api, {
    cuentas: vi.fn().mockResolvedValue([{ id: 'c1', nombre: 'Bancolombia', saldo: 1_000_000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]),
    movimientos: vi.fn().mockResolvedValue([
      { id: 'm1', fecha: '2026-10-02T12:00:00', descripcion: 'Éxito', categoria: 'Mercado', tipo: 'expense', monto: 80000 },
    ]),
    reporteMensual: vi.fn().mockResolvedValue({ salud: { score: 80, tips: ['ok'] }, top_categorias: [{ categoria: 'Mercado', monto: 80000 }] }),
    disponibleHoy: vi.fn().mockResolvedValue({ categorias: [] }),
    enMiBolsillo: vi.fn().mockResolvedValue({
      saldo_total: 1_000_000, recurrentes_pendientes_mes: 0, aportes_comprometidos_mes: 0,
      disponible_real: 400_000, disponible_real_por_dia: 25_000,
    }),
    gmailEstado: vi.fn().mockResolvedValue({ conectado: true }),
    saludFinanciera: vi.fn().mockResolvedValue(null),
    sincronizacionEstado: vi.fn().mockResolvedValue({ tareas: [{}, {}, {}] }),
    tendencias: vi.fn().mockResolvedValue({
      meses: [
        { mes: '2026-05', gastos: 1_000_000 },
        { mes: '2026-06', gastos: 1_200_000 },
        { mes: '2026-07', gastos: 900_000 },
        { mes: '2026-08', gastos: 1_100_000 },
      ],
    }),
  })
})

describe('Inicio — bloque protagonista y dos acciones', () => {
  it('muestra «Puedes gastar hoy», el estado de cuadre y el saldo total', async () => {
    montar()
    const hero = await screen.findByRole('region', { name: 'Cuánto puedes gastar hoy' })
    expect(within(hero).getByText('Puedes gastar hoy')).toBeInTheDocument()
    expect(hero).toHaveTextContent(/25\.000/)
    expect(within(hero).getByText('Tus cuentas cuadran')).toBeInTheDocument()
    expect(within(hero).getByText(/Saldo total/)).toBeInTheDocument()
  })

  it('ofrece exactamente dos acciones principales y las demás secciones empiezan plegadas', async () => {
    montar()
    await screen.findByText('Puedes gastar hoy')
    expect(screen.getByRole('link', { name: /Agregar movimiento/ })).toHaveAttribute('href', '/agregar')
    expect(screen.getByRole('link', { name: /Traer movimientos/ })).toHaveAttribute('href', '/sincronizacion')
    for (const nombre of ['Cuentas', 'Movimientos recientes', 'Por resolver', 'Presupuesto del mes', 'Salud financiera', 'Accesos', 'Recomendaciones']) {
      expect(screen.getByRole('button', { name: new RegExp(nombre) })).toHaveAttribute('aria-expanded', 'false')
    }
    // Lo plegado no se monta: nada de Patrimonio, Metas ni el mazo de cuentas a la vista
    expect(screen.queryByRole('link', { name: 'Patrimonio' })).toBeNull()
    expect(screen.queryByText('Disponible real este mes')).toBeNull()
  })

  it('el número de tareas aparece en «Traer movimientos»', async () => {
    montar()
    const enlace = await screen.findByRole('link', { name: /Traer movimientos/ })
    await waitFor(() => expect(enlace).toHaveTextContent('3'))
  })
})

describe('Inicio — secciones plegables que recuerdan su estado', () => {
  it('al abrir una sección muestra su contenido y guarda el estado en localStorage', async () => {
    montar()
    const boton = await screen.findByRole('button', { name: /Presupuesto del mes/ })
    await userEvent.click(boton)
    expect(boton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('= Disponible real este mes')).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('cuadrame:inicio-secciones')).presupuesto).toBe(true)
  })

  it('al volver a Inicio la sección sigue abierta; plegarla también se recuerda', async () => {
    localStorage.setItem('cuadrame:inicio-secciones', JSON.stringify({ accesos: true }))
    const { unmount } = montar()
    const boton = await screen.findByRole('button', { name: /Accesos/ })
    expect(boton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: 'Patrimonio' })).toBeInTheDocument()
    await userEvent.click(boton)
    expect(boton).toHaveAttribute('aria-expanded', 'false')
    expect(JSON.parse(localStorage.getItem('cuadrame:inicio-secciones')).accesos).toBe(false)
    unmount()
    montar()
    expect(await screen.findByRole('button', { name: /Accesos/ })).toHaveAttribute('aria-expanded', 'false')
  })

  it('sin localStorage (modo privado) la sección funciona igual con su valor por defecto', async () => {
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })
    montar(
      <SeccionPlegable id="x" titulo="Prueba" abiertaPorDefecto>
        <p>Contenido</p>
      </SeccionPlegable>
    )
    const boton = screen.getByRole('button', { name: /Prueba/ })
    expect(boton).toHaveAttribute('aria-expanded', 'true')
    await userEvent.click(boton)
    expect(boton).toHaveAttribute('aria-expanded', 'false')
    getItem.mockRestore()
    setItem.mockRestore()
  })

  it('sin movimientos, la sección de movimientos arranca abierta con la invitación a registrar el primero', async () => {
    api.movimientos.mockResolvedValue([])
    montar()
    expect(await screen.findByText('Aún no tienes movimientos registrados')).toBeInTheDocument()
  })
})

describe('Inicio — tendencia del gasto', () => {
  it('dibuja una mini gráfica con rol de imagen y un resumen en texto', async () => {
    montar()
    const grafica = await screen.findByRole('img', { name: /Gasto mensual, últimos 4 meses: de .*1\.000\.000.* a .*1\.100\.000.*sube 10 %/ })
    expect(grafica).toBeInTheDocument()
    expect(screen.getByTestId('tendencia-gasto')).toHaveTextContent('Tu gasto mensual')
  })

  it('sin datos de tendencia no dibuja nada (ni rompe)', async () => {
    api.tendencias.mockResolvedValue({ meses: [] })
    montar()
    await screen.findByText('Puedes gastar hoy')
    expect(screen.queryByTestId('sparkline')).toBeNull()
  })
})
