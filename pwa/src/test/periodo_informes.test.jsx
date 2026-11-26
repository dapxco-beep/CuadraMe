import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

import { etiquetaRango, rangoPeriodo } from '../lib/informe'
import {
  esUnMes, leerValor, mesDeValor, paramsApi, valorDe, valorDeAnio, valorDeMes, ventanaHistorial,
} from '../lib/periodoInforme'

// «Hoy» fijo para que las cuentas sean verificables a mano: jueves 15 de octubre de 2026.
const HOY = new Date(2026, 9, 15)

describe('periodos predefinidos (calculados a mano)', () => {
  it('6 meses: del 1 de mayo al 15 de octubre (6 meses de calendario)', () => {
    expect(rangoPeriodo('6_meses', HOY)).toEqual({ desde: '2026-05-01', hasta: '2026-10-15' })
  })
  it('año pasado: el 2025 completo', () => {
    expect(rangoPeriodo('anio_pasado', HOY)).toEqual({ desde: '2025-01-01', hasta: '2025-12-31' })
  })
  it('los que ya existían no cambian', () => {
    expect(rangoPeriodo('este_mes', HOY)).toEqual({ desde: '2026-10-01', hasta: '2026-10-15' })
    expect(rangoPeriodo('mes_pasado', HOY)).toEqual({ desde: '2026-09-01', hasta: '2026-09-30' })
    expect(rangoPeriodo('3_meses', HOY)).toEqual({ desde: '2026-08-01', hasta: '2026-10-15' })
    expect(rangoPeriodo('anio', HOY)).toEqual({ desde: '2026-01-01', hasta: '2026-10-15' })
  })
  it('un mes calendario: el pasado completo; el actual es «este mes» (hasta hoy)', () => {
    expect(valorDeMes('2026-02', HOY)).toEqual({ periodo: 'rango', desde: '2026-02-01', hasta: '2026-02-28' })
    expect(valorDeMes('2028-02', new Date(2029, 0, 1))).toEqual({ periodo: 'rango', desde: '2028-02-01', hasta: '2028-02-29' }) // bisiesto
    expect(valorDeMes('2026-10', HOY).periodo).toBe('este_mes')
  })
  it('un año: el actual llega hasta hoy; uno pasado va completo', () => {
    expect(valorDeAnio(2026, HOY)).toEqual({ periodo: 'anio', desde: '2026-01-01', hasta: '2026-10-15' })
    expect(valorDeAnio(2024, HOY)).toEqual({ periodo: 'rango', desde: '2024-01-01', hasta: '2024-12-31' })
  })
})

describe('parámetros para la API', () => {
  it('los periodos que el servidor conoce van por su nombre', () => {
    for (const id of ['este_mes', 'mes_pasado', '3_meses', 'anio']) expect(paramsApi(valorDe(id, HOY))).toEqual({ periodo: id })
  })
  it('6 meses y año pasado van como rango con sus fechas', () => {
    expect(paramsApi(valorDe('6_meses', HOY))).toEqual({ periodo: 'rango', desde: '2026-05-01', hasta: '2026-10-15' })
    expect(paramsApi(valorDe('anio_pasado', HOY))).toEqual({ periodo: 'rango', desde: '2025-01-01', hasta: '2025-12-31' })
  })
  it('un mes completo se pide como «mes» (el servidor lo nombra y lo compara con el anterior)', () => {
    expect(paramsApi(valorDeMes('2026-07', HOY))).toEqual({ periodo: 'mes', mes: '2026-07' })
    expect(paramsApi({ periodo: 'rango', desde: '2026-07-02', hasta: '2026-07-31' })).toEqual({ periodo: 'rango', desde: '2026-07-02', hasta: '2026-07-31' })
  })
})

describe('el mes que usan «Mi mes», «Cierre» e «Impuestos»', () => {
  it('Mi mes: el mes en que termina el periodo', () => {
    expect(mesDeValor(valorDe('3_meses', HOY))).toBe('2026-10')
    expect(mesDeValor(valorDe('mes_pasado', HOY))).toBe('2026-09')
  })
  it('Cierre: nunca el mes en curso (se cierra un mes terminado)', () => {
    expect(mesDeValor(valorDe('este_mes', HOY), { terminado: true, hoy: HOY })).toBe('2026-09')
    expect(mesDeValor(valorDe('mes_pasado', HOY), { terminado: true, hoy: HOY })).toBe('2026-09')
    expect(mesDeValor(valorDe('anio_pasado', HOY), { terminado: true, hoy: HOY })).toBe('2025-12')
    expect(mesDeValor(valorDe('este_mes', new Date(2027, 0, 5)), { terminado: true, hoy: new Date(2027, 0, 5) })).toBe('2026-12') // cruza de año
  })
  it('esUnMes distingue un mes de un periodo de varios', () => {
    expect(esUnMes(valorDe('este_mes', HOY), HOY)).toBe(true)
    expect(esUnMes(valorDe('mes_pasado', HOY), HOY)).toBe(true)
    expect(esUnMes(valorDe('3_meses', HOY), HOY)).toBe(false)
    expect(esUnMes({ periodo: 'rango', desde: '2026-09-02', hasta: '2026-09-30' }, HOY)).toBe(false)
  })
  it('Patrimonio: la ventana de historia es el periodo, ampliado a 6 meses si es más corto', () => {
    expect(ventanaHistorial(valorDe('este_mes', HOY))).toEqual({ desde: '2026-05', hasta: '2026-10' })
    expect(ventanaHistorial(valorDe('anio', HOY))).toEqual({ desde: '2026-01', hasta: '2026-10' })
    expect(ventanaHistorial({ periodo: 'rango', desde: '2026-02-01', hasta: '2026-02-28' })).toEqual({ desde: '2025-09', hasta: '2026-02' })
  })
})

describe('leer el periodo de la dirección', () => {
  const q = (s) => new URLSearchParams(s)
  it('sin nada, «Este mes»', () => expect(leerValor(q(''), HOY).periodo).toBe('este_mes'))
  it('un periodo con nombre', () => expect(leerValor(q('p=6_meses'), HOY)).toEqual({ periodo: '6_meses', desde: '2026-05-01', hasta: '2026-10-15' }))
  it('un rango válido', () => expect(leerValor(q('p=rango&desde=2026-03-01&hasta=2026-03-31'), HOY)).toEqual({ periodo: 'rango', desde: '2026-03-01', hasta: '2026-03-31' }))
  it('lo inválido cae en «Este mes» (rango al revés, nombre inventado, fechas rotas)', () => {
    expect(leerValor(q('p=rango&desde=2026-03-31&hasta=2026-03-01'), HOY).periodo).toBe('este_mes')
    expect(leerValor(q('p=inventado'), HOY).periodo).toBe('este_mes')
    expect(leerValor(q('p=rango&desde=hola&hasta=mundo'), HOY).periodo).toBe('este_mes')
  })
  it('el enlace viejo ?mes=AAAA-MM sigue funcionando', () => {
    expect(leerValor(q('mes=2026-07'), HOY)).toEqual({ periodo: 'rango', desde: '2026-07-01', hasta: '2026-07-31' })
    expect(leerValor(q('mes=2026-13'), HOY).periodo).toBe('este_mes')
  })
})

describe('etiqueta del rango', () => {
  it('se lee en español según lo que comparten las fechas', () => {
    expect(etiquetaRango('2026-10-01', '2026-10-15')).toBe('1 al 15 de octubre de 2026')
    expect(etiquetaRango('2026-08-01', '2026-10-15')).toBe('1 de agosto al 15 de octubre de 2026')
    expect(etiquetaRango('2025-11-03', '2026-02-10')).toBe('3 de noviembre de 2025 al 10 de febrero de 2026')
    expect(etiquetaRango('2026-10-15', '2026-10-15')).toBe('15 de octubre de 2026')
  })
})

// ── El periodo es UNO para todas las pestañas ────────────────────────────────────────────────
const Marca = (nombre) => function Pantalla() {
  const { search } = useLocation()
  return <div>{`PANTALLA-${nombre}|${search}`}</div>
}
vi.mock('../screens/Panorama', () => ({ default: Marca('RESUMEN') }))
vi.mock('../screens/Informe', () => ({ default: Marca('GASTOS') }))
vi.mock('../screens/Wrapped', () => ({ default: Marca('MIMES') }))
vi.mock('../screens/Patrimonio', () => ({ default: Marca('PATRIMONIO') }))
vi.mock('../screens/CierreMes', () => ({ default: Marca('CIERRE') }))
vi.mock('../screens/Impuestos', () => ({ default: Marca('IMPUESTOS') }))

import Informes from '../screens/Informes'

const montar = (ruta) =>
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes><Route path="/informes" element={<Informes />} /></Routes>
    </MemoryRouter>
  )

describe('Informes: un único selector de periodo', () => {
  it('muestra los 7 periodos y el rango que se está viendo', async () => {
    montar('/informes?tab=gastos&p=3_meses')
    const grupo = await screen.findByRole('group', { name: 'Periodo del informe' })
    expect(Array.from(grupo.querySelectorAll('button')).map((b) => b.textContent))
      .toEqual(['Este mes', 'Mes pasado', '3 meses', '6 meses', 'Este año', 'Año pasado', 'Personalizado'])
    expect(screen.getByRole('button', { name: '3 meses' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Aplica a todas las pestañas')).toBeInTheDocument()
  })

  it('elegir un periodo cambia la dirección y lo ven todas las pestañas', async () => {
    const user = userEvent.setup()
    montar('/informes?tab=gastos')
    await screen.findByText(/PANTALLA-GASTOS/)
    await user.click(screen.getByRole('button', { name: '6 meses' }))
    expect((await screen.findByText(/PANTALLA-GASTOS/)).textContent).toContain('p=6_meses')
    for (const [pestana, marca] of [['Cierre', 'CIERRE'], ['Mi mes', 'MIMES'], ['Resumen', 'RESUMEN']]) {
      await user.click(screen.getByRole('tab', { name: pestana }))
      const texto = (await screen.findByText(new RegExp(`PANTALLA-${marca}`))).textContent
      expect(texto).toContain('p=6_meses')
      expect(texto).toContain(`tab=${pestana === 'Resumen' ? 'panorama' : pestana === 'Mi mes' ? 'resumen' : pestana.toLowerCase()}`)
      expect(screen.getByRole('button', { name: '6 meses' })).toHaveAttribute('aria-pressed', 'true')
    }
  })

  it('Patrimonio e Impuestos (ocultos con el perfil Esencial) también reciben el periodo si se abren por enlace', async () => {
    for (const [tab, marca] of [['patrimonio', 'PATRIMONIO'], ['impuestos', 'IMPUESTOS']]) {
      const { unmount } = montar(`/informes?tab=${tab}&p=6_meses`)
      const texto = (await screen.findByText(new RegExp(`PANTALLA-${marca}`))).textContent
      expect(texto).toContain('p=6_meses')
      expect(screen.getByRole('button', { name: '6 meses' })).toHaveAttribute('aria-pressed', 'true')
      unmount()
    }
  })

  it('el rango personalizado se guarda con sus fechas y vuelve a «Este mes» si se borra', async () => {
    const user = userEvent.setup()
    montar('/informes?tab=gastos&p=rango&desde=2026-03-01&hasta=2026-03-31')
    const marca = await screen.findByText(/PANTALLA-GASTOS/)
    expect(marca.textContent).toContain('desde=2026-03-01')
    expect(screen.getByLabelText('Desde')).toHaveValue('2026-03-01')
    await user.click(screen.getByRole('button', { name: 'Este mes' }))
    const despues = (await screen.findByText(/PANTALLA-GASTOS/)).textContent
    expect(despues).toContain('p=este_mes')
    expect(despues).not.toContain('desde=')
  })

  it('un enlace viejo con ?mes= se entiende como ese mes', async () => {
    montar('/informes?tab=gastos&mes=2026-07')
    expect(await screen.findByRole('region', { name: 'Periodo del informe' })).toHaveTextContent('1 al 31 de julio de 2026')
  })
})
