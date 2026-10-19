// Extracto de la tarjeta de Nu: el pago es UNA fila por el monto A, con «cómo se aplicó»; y arriba, si lo leído suma
// lo que dice el extracto. Datos inventados.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { render as renderBase, screen } from '@testing-library/react'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Nu Tarjeta', tipo: 'credito' }], recargar: vi.fn() }),
}))

import SubidaMultiple from '../components/SubidaMultiple'
import { clavesFaltantes, filasResumenTarjeta, normalizarPdf, resumenPrevio, textoCorreccion, textoCorrecciones, textoPagoAplicado } from '../lib/subidaMultiple'

const render = (ui) => renderBase(<MemoryRouter>{ui}</MemoryRouter>)
const DETALLE = { capital: 590000, intereses: 0, cargos: 10000, aplicado: [400000, 200000] }
const pago = (extra) => ({
  fecha: '2026-10-05', descripcion: 'Pago de tu tarjeta', monto: 600000, tipo: 'income', estado: 'faltante',
  fingerprint: 'fp-pago', categoria_sugerida: 'Pago de tarjeta', pago_tarjeta: true, pista: 'posible_traslado_propio',
  pago_detalle: DETALLE, ...extra,
})
const RESUMEN = { deuda_a_pagar: 408000, pago_minimo: 65000, limite_pago: '2026-11-04', corte: '2026-10-15', cupo: 1000000,
  periodo: { inicio: '2026-09-14', fin: '2026-10-14' }, usado: null }
const respuesta = (items, extra) => ({
  ok: true, historial_id: 'h1', cuenta_id: 'c1', banco_detectado: 'nu', total_movimientos: items.length, review: items,
  mensaje_lectura: 'Leí 17 líneas y suman lo que dice tu extracto ✓', lectura_completa: true, resumen_tarjeta: RESUMEN, ...extra,
})

describe('pago de la tarjeta de Nu', () => {
  beforeEach(() => {
    Object.keys(api).forEach((k) => delete api[k])
    api.importarFaltantes = vi.fn().mockResolvedValue({ ok: true, importados: 1 })
  })

  it('el texto dice cómo se aplicó el pago', () => {
    const t = textoPagoAplicado(DETALLE)
    expect(t.principal.replace(/\s/g, ' ')).toMatch(/^Cómo se aplicó este pago: capital \$ ?590\.000 · intereses \$ ?0 · cargos \$ ?10\.000$/)
    expect(t.aplicado.replace(/\s/g, ' ')).toMatch(/^Se aplicó \$ ?400\.000 y \$ ?200\.000\.$/)
    expect(textoPagoAplicado(null)).toBeNull()
    expect(textoPagoAplicado({ aplicado: [27000] }).aplicado.replace(/\s/g, ' ')).toMatch(/^Se aplicó \$ ?27\.000\.$/)
  })

  it('el resumen de la página 1 solo muestra lo que se leyó', () => {
    const filas = filasResumenTarjeta(RESUMEN).map(([k]) => k)
    expect(filas).toEqual(['Deuda a pagar este mes', 'Pago mínimo', 'Fecha límite de pago', 'Fecha de corte', 'Periodo facturado', 'Cupo'])
    expect(filasResumenTarjeta(null)).toEqual([])
  })

  it('con salida igual en ahorros viene marcado; sin certeza queda apagado y fuera de «seleccionar todo»', () => {
    const encendido = normalizarPdf(respuesta([pago({ marcar_por_defecto: true })]))
    const apagado = normalizarPdf(respuesta([pago({ marcar_por_defecto: false, aviso_linea: 'Parece el pago de tu tarjeta. Confirma el monto.' })]))
    expect(clavesFaltantes([{ id: 'a', estado: 'listo', ...encendido }])).toEqual(['a:fp-pago'])
    expect(clavesFaltantes([{ id: 'a', estado: 'listo', ...apagado }])).toEqual([])
    expect(apagado.items[0]).toMatchObject({ pagoDetalle: DETALLE, apagada: true })
    expect(apagado).toMatchObject({ lecturaCompleta: true, mensajeLectura: 'Leí 17 líneas y suman lo que dice tu extracto ✓' })
  })

  it('la hoja muestra cuántas líneas leyó, el resumen, cómo se aplicó el pago y el aviso; la casilla queda apagada', async () => {
    api.obtenerReviewExtracto = vi.fn().mockResolvedValue(respuesta([pago({
      marcar_por_defecto: false, aviso_linea: 'Parece el pago de tu tarjeta. Confirma el monto.' })]))
    render(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} onCancelar={() => {}} />)
    const casilla = await screen.findByRole('checkbox', { name: /Importar Pago de tu tarjeta/ })
    expect(casilla).not.toBeChecked()
    expect(casilla).toBeEnabled()
    expect(screen.getByTestId('mensaje-lectura')).toHaveTextContent('Leí 17 líneas y suman lo que dice tu extracto')
    expect(screen.getByTestId('datos-resumen-tarjeta')).toHaveTextContent('Deuda a pagar este mes')
    expect(screen.getByTestId('pago-aplicado')).toHaveTextContent(/Cómo se aplicó este pago/)
    expect(screen.getByTestId('pago-se-aplico')).toHaveTextContent(/Se aplicó/)
    expect(screen.getByTestId('aviso-pago-tarjeta')).toHaveTextContent('Parece el pago de tu tarjeta. Confirma el monto.')
  })

  it('si no cuadra, lo dice como alerta con lo que falta', async () => {
    api.obtenerReviewExtracto = vi.fn().mockResolvedValue(respuesta([pago({ marcar_por_defecto: true })], {
      lectura_completa: false,
      mensaje_lectura: 'Leí 16 líneas pero faltan $5.000 para sumar lo que dice tu extracto. Revisa antes de importar' }))
    render(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} onCancelar={() => {}} />)
    const aviso = await screen.findByTestId('mensaje-lectura')
    expect(aviso).toHaveTextContent('faltan $5.000')
    expect(aviso).toHaveAttribute('role', 'alert')
  })

  it('corregir_monto viene encendido y dice cómo se corrige; quitar_repetido ofrece quitar el pago repetido', () => {
    const det = { capital: 697534.97, intereses: 0, cargos: 0, aplicado: [474542, 222992.97] }
    const corr = normalizarPdf(respuesta([pago({ monto: 697534.97, pago_detalle: det, estado: 'corregir_monto', monto_anterior: 474542, marcar_por_defecto: true })]))
    const it = corr.items[0]
    expect(it).toMatchObject({ estado: 'nuevo', apagada: false, correccion: { tipo: 'corregir', anterior: 474542 } })
    expect(clavesFaltantes([{ id: 'a', estado: 'listo', ...corr }])).toEqual(['a:fp-pago'])
    expect(textoCorreccion(it).titulo.replace(/\s/g, ' ')).toBe(
      'Corrige tu pago del 5 oct: pasa de $474.542 a $697.534,97 (es lo que pagaste; $474.542 y $222.992,97 son cómo se aplicó)')
    const rep = normalizarPdf(respuesta([pago({ monto: 474542, estado: 'quitar_repetido', monto_correcto: 697534.97, marcar_por_defecto: true })])).items[0]
    expect(textoCorreccion(rep).titulo.replace(/\s/g, ' ')).toBe('Quitar el pago repetido de $474.542')
    expect(textoCorreccion(rep).detalle).toMatch(/dos pagos del 5 oct/)
    expect(textoCorreccion(pago({}))).toBeNull()
    const r = resumenPrevio([it, rep])
    expect(r).toMatchObject({ correcciones: 2, nuevos: 0 })
    expect(textoCorrecciones(1)).toBe('1 corrección')
  })

  it('la hoja muestra la línea de corrección y «1 corrección» en el resumen', async () => {
    api.obtenerReviewExtracto = vi.fn().mockResolvedValue(respuesta([pago({
      estado: 'corregir_monto', monto_anterior: 400000, marcar_por_defecto: true })]))
    render(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} onCancelar={() => {}} />)
    expect(await screen.findByTestId('linea-correccion')).toHaveTextContent(/Corrige tu pago del 5 oct: pasa de \$ ?400\.000 a \$ ?600\.000/)
    expect(screen.getByTestId('previo-correcciones')).toHaveTextContent('1 corrección')
  })
})
