// «Completar mis extractos: rendimientos e impuestos»: textos, botón único, vista previa con el total, avance y resultado;
// y el Cierre de mes que muestra los rendimientos dentro de los ingresos. Números inventados.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({ previaRendimientos: vi.fn(), registrarRendimientos: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({ useCuentas: () => ({ cuentas: [], recargar: vi.fn().mockResolvedValue() }) }))

import RegistrarRendimientos from '../components/RegistrarRendimientos'
import CierreExtractos from '../components/CierreExtractos'
import { formatMoneda } from '../lib/format'
import {
  avisoExtracto, juntarResultados, lineaExtracto, lineaResultado, resumenFinal, textoBoton, textoProgreso, textoTotal,
} from '../lib/registrarRendimientos'

const fmt = (n) => `$${n}`
const EXT = (mes, monto, extra = {}) => ({
  historial_id: `h-${mes}`, mes, cuenta: { id: 'nu', nombre: 'Nu Colombia' }, monto, estimado: true, releera: true,
  puede_releerse: true, requiere_clave: false, ...extra,
})
const PREVIA = { total: 2, total_pesos: 17000, aproximado: true, maximo_por_llamada: 12, extractos: [EXT('2026-09', 9000), EXT('2026-10', 8000)] }
const PASO = (mes, monto, extra = {}) => ({
  restantes: 0, resultados: [{ historial_id: `h-${mes}`, mes, estado: 'registrado', monto, motivo: null, ...extra }],
})

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  api.previaRendimientos.mockResolvedValue(PREVIA)
})

describe('textos', () => {
  it('botón, línea por extracto, total y avisos', () => {
    expect(textoBoton(2)).toBe('Completar mis extractos: rendimientos e impuestos (2)')
    expect(lineaExtracto(EXT('2026-09', 9000), fmt)).toBe('Septiembre 2026 · Nu Colombia · unos $9000')
    expect(lineaExtracto(EXT('2026-09', 9000, { estimado: false }), fmt)).toBe('Septiembre 2026 · Nu Colombia · $9000')
    expect(textoTotal(PREVIA, fmt)).toBe('En total, unos $17000. El valor exacto sale de leer cada extracto otra vez.')
    expect(textoTotal({ total_pesos: 9000, aproximado: false }, fmt)).toBe('En total, $9000.')
    expect(avisoExtracto(EXT('2026-09', 1, { requiere_clave: true }))).toContain('clave de tu PDF')
    expect(avisoExtracto(EXT('2026-09', 1, { puede_releerse: false }))).toContain('Conecta Gmail')
    expect(avisoExtracto(EXT('2026-09', 1, { releera: false }))).toBe('')
  })

  it('la previa exacta dice cuánto de cada concepto; lo estimado, aparte', () => {
    const e = EXT('2026-08', 19500, { estimado: false, conceptos: { rendimientos: 9000, impuesto_4x1000: 4000, costos_retiro: 6500 } })
    expect(lineaExtracto(e, fmt)).toBe('Agosto 2026 · Nu Colombia · $9000 de rendimientos, $4000 de 4x1000 y $6500 de costos por retiro')
    const p = { total: 2, total_pesos: 28600, aproximado: true, por_concepto: { rendimientos: 9000, impuesto_4x1000: 4000, costos_retiro: 6500 }, por_determinar: 9100 }
    expect(textoTotal(p, fmt)).toBe('En total, $9000 de rendimientos, $4000 de 4x1000 y $6500 de costos por retiro. Además, unos $9100 que salen de leer cada extracto otra vez.')
    expect(textoTotal({ ...p, por_determinar: 0, aproximado: false }, fmt)).toBe('En total, $9000 de rendimientos, $4000 de 4x1000 y $6500 de costos por retiro.')
  })

  it('progreso, resumen y resultados', () => {
    expect(textoProgreso(1, 2)).toBe('Completando 1 de 2…')
    expect(resumenFinal({ registrados: 2, total: 17000 }, fmt)).toBe('Completé 2 extractos: $17000.')
    expect(resumenFinal({ registrados: 2, porConcepto: { rendimientos: 17000, impuesto_4x1000: 4400, costos_retiro: 6500 } }, fmt))
      .toBe('Completé 2 extractos: $17000 de rendimientos, $4400 de 4x1000 y $6500 de costos por retiro.')
    expect(resumenFinal({}, fmt)).toBe('Tus extractos ya están completos. No cambié nada.')
    const j = juntarResultados([PASO('2026-09', 9000), PASO('2026-10', 0, { estado: 'saltado', motivo: 'No pudimos abrir el PDF.' })], 0, fmt)
    expect(j).toMatchObject({ registrados: 1, saltados: 1, total: 9000 })
    expect(j.resumen).toBe('Completé 1 extracto: $9000 de rendimientos. 1 extracto quedó para después.')
    expect(lineaResultado(j.resultados[0], fmt)).toBe('Septiembre 2026: $9000 de rendimientos registrados')
    const c = { rendimientos: 9000, impuesto_4x1000: 4000, costos_retiro: 6500 }
    expect(lineaResultado({ ...j.resultados[0], conceptos: c }, fmt)).toBe('Septiembre 2026: $9000 de rendimientos, $4000 de 4x1000 y $6500 de costos por retiro registrados')
    expect(lineaResultado(j.resultados[1], fmt)).toBe('Octubre 2026: para después. No pudimos abrir el PDF.')
  })
})

describe('<RegistrarRendimientos>', () => {
  const montar = (props = {}) => render(<MemoryRouter><RegistrarRendimientos {...props} /></MemoryRouter>)

  it('sin nada que registrar, o si la previa falla, no dibuja nada', async () => {
    api.previaRendimientos.mockResolvedValue({ total: 0, extractos: [] })
    const a = montar()
    await waitFor(() => expect(api.previaRendimientos).toHaveBeenCalled())
    expect(a.container).toBeEmptyDOMElement()
    cleanup()
    api.previaRendimientos.mockRejectedValue(new Error('x'))
    const b = montar()
    await waitFor(() => expect(api.previaRendimientos).toHaveBeenCalledTimes(2))
    expect(b.container).toBeEmptyDOMElement()
  })

  it('la previa muestra la lista y el total; nada cambia hasta confirmar', async () => {
    montar()
    await userEvent.click(await screen.findByRole('button', { name: /Completar mis extractos: rendimientos e impuestos \(2\)/ }))
    expect(screen.getByText(/Septiembre 2026 · Nu Colombia · unos \$\s?9\.000/)).toBeInTheDocument()
    expect(screen.getByTestId('total-rendimientos')).toHaveTextContent(/En total, unos \$\s?17\.000/)
    expect(api.registrarRendimientos).not.toHaveBeenCalled()
  })

  it('registra de a uno con avance y muestra el resumen', async () => {
    const onListo = vi.fn()
    let liberar
    api.registrarRendimientos
      .mockImplementationOnce(() => new Promise((res) => { liberar = () => res(PASO('2026-09', 9000)) }))
      .mockResolvedValueOnce(PASO('2026-10', 8000))
    montar({ onListo })
    await userEvent.click(await screen.findByTestId('registrar-rendimientos'))
    await userEvent.click(screen.getByRole('button', { name: 'Sí, completar' }))
    expect(await screen.findByTestId('progreso-rendimientos')).toHaveTextContent('Completando 1 de 2…')
    liberar()
    expect(await screen.findByTestId('resumen-rendimientos')).toHaveTextContent(/Completé 2 extractos: \$\s?17\.000 de rendimientos\./)
    expect(api.registrarRendimientos).toHaveBeenNthCalledWith(1, { maximo: 1, excluir: [], continuar: false })
    expect(api.registrarRendimientos).toHaveBeenNthCalledWith(2, { maximo: 1, excluir: ['h-2026-09'], continuar: true })
    expect(onListo).toHaveBeenCalled()
  })

  it('un extracto saltado se dice, y si falla a la mitad cuenta lo que sí quedó hecho', async () => {
    api.registrarRendimientos
      .mockResolvedValueOnce(PASO('2026-09', 9000))
      .mockResolvedValueOnce(PASO('2026-10', 0, { estado: 'saltado', motivo: 'No pudimos abrir el PDF. No cambié nada.' }))
    montar()
    await userEvent.click(await screen.findByTestId('registrar-rendimientos'))
    await userEvent.click(screen.getByRole('button', { name: 'Sí, completar' }))
    expect(await screen.findByTestId('resumen-rendimientos')).toHaveTextContent('1 extracto quedó para después')
    expect(screen.getByText(/Octubre 2026: para después\. No pudimos abrir el PDF/)).toBeInTheDocument()
    cleanup()
    api.registrarRendimientos.mockReset()
    api.registrarRendimientos.mockResolvedValueOnce(PASO('2026-09', 9000)).mockRejectedValueOnce(new Error('Failed to fetch'))
    montar()
    await userEvent.click(await screen.findByTestId('registrar-rendimientos'))
    await userEvent.click(screen.getByRole('button', { name: 'Sí, completar' }))
    expect(await screen.findByTestId('resumen-rendimientos')).toHaveTextContent('Completé 1 extracto')
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})

describe('Cierre de mes con rendimientos', () => {
  const fmtM = (v, m) => formatMoneda(v, m || 'COP').replace(/\s/g, ' ')
  const cuenta = (o = {}) => ({
    cuenta_id: 'c1', nombre: 'Nu Colombia', tipo: 'ahorro', tarjeta: false, moneda: 'COP', estado: 'cuadra', sin_extracto: false,
    etiqueta_extracto: null, periodo: { desde: '2026-09-01', hasta: '2026-09-30', mes_completo: true },
    empece: 1000000, empece_origen: 'extracto', ingresos: 509000, rendimientos: 9000, gastos: 200000, otros: 0, otros_detalle: [],
    otros_total_movimientos: 0, termine: 1309000, segun_extracto: 1309000, diferencia: 0, historial_id: 'h1', causas: [], acciones: [],
    motivo: null, base: {}, ...o,
  })
  const datos = (c) => ({
    mes: '2026-09', etiqueta: 'Septiembre 2026', parcial: false, moneda_base: 'COP', monedas_sin_tasa: [], meses: [], hay_datos: true,
    resumen_bancos: [{ banco: 'Nu', estado: 'cuadra', diferencia: 0 }],
    bancos: [{ banco: 'Nu', estado: 'cuadra', diferencia: 0, cuentas: [c], total: {} }],
    total: { empece: 1000000, ingresos: 509000, rendimientos: 9000, gastos: 200000, otros: 0, termine: 1309000, cuentas: 1, cuadran: 1, no_cuadran: 0, sin_extracto: 0 },
  })

  it('los ingresos incluyen los rendimientos y se dice cuánto fue', () => {
    render(<MemoryRouter><CierreExtractos datos={datos(cuenta())} /></MemoryRouter>)
    expect(screen.getByTestId('cierre-cuenta')).toHaveTextContent(`Incluye ${fmtM(9000, 'COP')} de rendimientos`)
    expect(screen.getByTestId('cierre-total')).toHaveTextContent('de rendimientos')
    expect(screen.getAllByText('Cuadra').length).toBeGreaterThan(0)
  })

  it('los gastos incluyen el 4x1000 y los costos por retiro, con detalle que se abre', async () => {
    const detalle = [
      { concepto: 'rendimientos', fecha: '2026-09-30', descripcion: 'Rendimientos de tu cuenta Nu · septiembre de 2026', monto: 9000 },
      { concepto: 'impuesto_4x1000', fecha: '2026-09-30', descripcion: 'Impuesto 4x1000 (GMF) · septiembre de 2026', monto: 4000 },
    ]
    render(<MemoryRouter><CierreExtractos datos={datos(cuenta({ impuesto_4x1000: 4000, costos_retiro: 6500, detalle_resumen: detalle }))} /></MemoryRouter>)
    const c = screen.getByTestId('cierre-cuenta')
    expect(c).toHaveTextContent(`Incluye ${fmtM(4000, 'COP')} de impuesto 4x1000 y ${fmtM(6500, 'COP')} de costos por retiro`)
    expect(screen.queryByTestId('detalle-resumen')).toBeNull()
    await userEvent.click(screen.getByTestId('detalle-resumen-boton'))
    expect(screen.getByTestId('detalle-resumen')).toHaveTextContent('Impuesto 4x1000 (GMF) · septiembre de 2026')
  })

  it('sin rendimientos no aparece la nota', () => {
    render(<MemoryRouter><CierreExtractos datos={datos(cuenta({ rendimientos: 0 }))} /></MemoryRouter>)
    expect(screen.getByTestId('cierre-cuenta')).not.toHaveTextContent('de rendimientos')
  })
})
