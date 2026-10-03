// Planificación: ayudas puras con números verificados a mano + componentes con la API simulada.
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ categorias: [], nombres: ['Comida', 'Ocio'], iconoDe: () => '💳', cargando: false, recargar: vi.fn() }),
}))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Banco', saldo: 1, moneda: 'COP' }], recargar: vi.fn() }),
}))

import {
  altoSegmento, colorEstado, diaAnterior, escalaDescomposicion, etiquetaPeriodo, posicionesBarra, textoRango,
} from '../lib/planificacion'
import BarraProyeccion from '../components/BarraProyeccion'
import GraficoDescomposicion from '../components/GraficoDescomposicion'
import SugerenciaIngreso from '../components/SugerenciaIngreso'
import PlanificadorMeta, { finDeMes } from '../components/PlanificadorMeta'
import Presupuesto from '../screens/Presupuesto'

describe('ayudas puras', () => {
  it('fechas y periodos', () => {
    expect(diaAnterior('2026-03-01')).toBe('2026-02-28')
    expect(diaAnterior('2026-01-01')).toBe('2025-12-31')
    expect(textoRango('2026-10-16', '2026-11-01')).toBe('16 oct – 31 oct')
    expect(textoRango('2026-10-01', '2026-10-16')).toBe('1 oct – 15 oct')
    expect(etiquetaPeriodo('biweekly')).toBe('Quincenal')
    expect(etiquetaPeriodo('monthly')).toBe('Mensual')
    expect(etiquetaPeriodo('lo-que-sea')).toBe('Mensual')
    expect(finDeMes('2027-12')).toBe('2027-12-31T12:00:00')
    expect(finDeMes('2028-02')).toBe('2028-02-29T12:00:00') // 2028 es bisiesto
  })

  it('posiciones de la barra: 280.000 de 400.000 con cierre en 560.000', () => {
    const p = posicionesBarra({ limite: 400000, gastado: 280000, proyectado: 560000 })
    expect(p.usado).toBe(70)
    expect(p.marcador).toBe(100) // 140 % -> pegado al borde
    expect(p.desborda).toBe(true)
    const q = posicionesBarra({ limite: 400000, gastado: 100000, proyectado: 200000 })
    expect([q.usado, q.marcador, q.desborda]).toEqual([25, 50, false])
    expect(posicionesBarra({ limite: 0, gastado: 5 }).marcador).toBeNull()
  })

  it('colores por estado', () => {
    expect(colorEstado('en_riesgo')).toBe('var(--color-danger)')
    expect(colorEstado('atencion')).toBe('var(--color-accent-2)')
    expect(colorEstado('bien')).toBe('var(--color-accent)')
  })

  it('escala de la descomposición', () => {
    const meses = [
      { ahorro: 900000, valorizacion: 600000, reduccion_deuda: 500000 }, // +2.000.000 arriba
      { ahorro: -100000, valorizacion: -500000, reduccion_deuda: 200000 }, // +200.000 / -600.000
    ]
    const e = escalaDescomposicion(meses)
    expect(e.maxArriba).toBe(2000000)
    expect(e.maxAbajo).toBe(600000)
    expect(e.pctArriba).toBeCloseTo((2000000 / 2600000) * 100, 6)
    expect(altoSegmento(900000, e)).toBe(45) // 900.000 / 2.000.000
    expect(altoSegmento(-500000, e)).toBeCloseTo((500000 / 600000) * 100, 6)
    expect(escalaDescomposicion([]).total).toBe(0)
  })
})

describe('componentes', () => {
  beforeEach(() => {
    for (const k of Object.keys(api)) delete api[k]
  })

  it('BarraProyeccion dibuja el marcador en el borde cuando te pasarías', () => {
    render(<BarraProyeccion item={{ limite: 400000, gastado: 280000, proyectado: 560000, estado: 'en_riesgo' }} />)
    expect(screen.getByTestId('marcador-proyeccion').style.left).toBe('100%')
  })

  it('BarraProyeccion pone el marcador a mitad de camino si cerrarías al 50 %', () => {
    render(<BarraProyeccion item={{ limite: 400000, gastado: 100000, proyectado: 200000, estado: 'bien' }} />)
    expect(screen.getByTestId('marcador-proyeccion').style.left).toBe('50%')
  })

  it('GraficoDescomposicion muestra los tres componentes del último mes', () => {
    render(<GraficoDescomposicion meses={[{ mes: '2026-09', neto_delta: 2000000, ahorro: 500000, valorizacion: 1000000, reduccion_deuda: 500000 }]} />)
    expect(screen.getByText('Ahorro')).toBeInTheDocument()
    expect(screen.getByText('Valorización')).toBeInTheDocument()
    expect(screen.getByText('Menos deuda')).toBeInTheDocument()
    expect(screen.getByTestId('grafico-descomposicion').textContent).toMatch(/2\.000\.000/)
  })

  it('SugerenciaIngreso muestra el reparto y solo aparta al confirmar', async () => {
    api.distribuirIngreso = vi.fn().mockResolvedValue({
      monto: 4000000, regla: { necesidades: 50, deseos: 30, ahorro: 20 },
      necesidades: 1800000, ahorro_total: 880000, gasto_libre: 1320000, ahorro_libre: 0,
      metas: [{ id: 'a', nombre: 'Viaje', monto: 400000 }, { id: 'b', nombre: 'Moto', monto: 480000 }],
      sobres: [{ categoria: 'Comida', monto: 792000 }], avisos: [],
    })
    api.aportarMeta = vi.fn().mockResolvedValue({})
    const onClose = vi.fn()
    render(<SugerenciaIngreso monto={4000000} cuentaId="c1" onClose={onClose} />)
    await screen.findByTestId('sugerencia-ingreso')
    expect(api.distribuirIngreso).toHaveBeenCalledWith(4000000)
    expect(screen.getByText(/Sobre Comida/)).toBeInTheDocument()
    expect(api.aportarMeta).not.toHaveBeenCalled() // sugerir no mueve plata
    await userEvent.click(screen.getByRole('button', { name: /Apartar para mis metas/ }))
    await waitFor(() => expect(api.aportarMeta).toHaveBeenCalledTimes(2))
    expect(api.aportarMeta).toHaveBeenCalledWith('a', 400000, 'c1')
    expect(api.aportarMeta).toHaveBeenCalledWith('b', 480000, 'c1')
    expect(onClose).toHaveBeenCalled()
  })

  it('PlanificadorMeta envía el mes como fin de mes y muestra la advertencia', async () => {
    api.planMeta = vi.fn().mockResolvedValue({
      viabilidad: 'incompatible', aporte_requerido: 1000000, capacidad_ahorro: 500000,
      advertencia: 'Necesitas ahorrar $1.000.000 al mes, pero solo te sobran unos $500.000.', mensaje: 'A tu ritmo la logras en 40 meses.',
    })
    render(<PlanificadorMeta onClose={() => {}} onCreada={() => {}} />)
    await userEvent.type(screen.getByLabelText('Monto que quieres reunir'), '12000000')
    await userEvent.type(screen.getByLabelText('Mes objetivo'), '2027-12')
    await userEvent.click(screen.getByRole('button', { name: /Calcular mi plan/ }))
    await screen.findByTestId('plan-meta')
    expect(api.planMeta).toHaveBeenCalledWith({
      objetivo: 12000000, fecha_objetivo: '2027-12-31T12:00:00', saldo_actual: 0, tasa_ea: 0,
    })
    expect(screen.getByText(/No cuadra con tus ingresos/)).toBeInTheDocument()
    expect(screen.getByText(/solo te sobran/)).toBeInTheDocument()
  })

  it('Presupuesto: mensaje de proyección, chip de quincena y marcador', async () => {
    api.presupuestos = vi.fn().mockResolvedValue([
      { id: 'p1', categoria: 'Ocio', limite: 400000, periodo: 'biweekly', alerta_pct: 80, sobre_ajuste: 0, activo: true },
    ])
    api.reporteMensual = vi.fn().mockResolvedValue({ top_categorias: [] })
    api.tendencias = vi.fn().mockResolvedValue({ meses: [] })
    api.flujoCajaFuturo = vi.fn().mockResolvedValue({ meses: [] })
    api.proyeccionPresupuestos = vi.fn().mockResolvedValue({
      config: { periodo_defecto: 'biweekly' },
      items: [{
        presupuesto_id: 'p1', categoria: 'Ocio', periodo: 'biweekly', inicio: '2026-10-16', fin: '2026-11-01',
        gastado: 280000, limite: 400000, proyectado: 560000, estado: 'en_riesgo', arrastre: 0,
        mensaje: 'Llevas 70% de Ocio y faltan 8 días; a este ritmo cerrarías en $560.000, $160.000 por encima del límite.',
      }],
    })
    render(<MemoryRouter><Presupuesto /></MemoryRouter>)
    expect(await screen.findByTestId('mensaje-proyeccion')).toHaveTextContent('cerrarías en $560.000')
    expect(screen.getByTestId('chip-periodo')).toHaveTextContent('Quincenal · 16 oct – 31 oct')
    expect(screen.getByTestId('marcador-proyeccion').style.left).toBe('100%')
  })

  it('Presupuesto sigue funcionando si la proyección falla (datos antiguos)', async () => {
    api.presupuestos = vi.fn().mockResolvedValue([
      { id: 'p1', categoria: 'Comida', limite: 500000, periodo: 'monthly', alerta_pct: 80, sobre_ajuste: 0, activo: true },
    ])
    api.reporteMensual = vi.fn().mockResolvedValue({ top_categorias: [{ categoria: 'Comida', monto: 100000 }] })
    api.tendencias = vi.fn().mockResolvedValue({ meses: [] })
    api.flujoCajaFuturo = vi.fn().mockResolvedValue({ meses: [] })
    api.proyeccionPresupuestos = vi.fn().mockRejectedValue(new Error('500'))
    render(<MemoryRouter><Presupuesto /></MemoryRouter>)
    expect(await screen.findByText('Comida')).toBeInTheDocument()
    expect(screen.queryByTestId('mensaje-proyeccion')).toBeNull()
  })
})
