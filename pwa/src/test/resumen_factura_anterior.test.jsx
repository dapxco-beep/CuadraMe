// Fila «resumen de la factura anterior» del extracto de tarjeta: tarjeta informativa + el pago de lo abonado como fila importable.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { render as renderBase, screen } from '@testing-library/react'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Nu Tarjeta', tipo: 'credito' }], recargar: vi.fn() }),
}))

import SubidaMultiple from '../components/SubidaMultiple'
import { clavesFaltantes, normalizarPdf, textoResumenFactura } from '../lib/subidaMultiple'

const render = (ui) => renderBase(<MemoryRouter>{ui}</MemoryRouter>)
const RESUMEN = { factura_anterior: 500000, pagado: 300000, saldo_pendiente: 200000 }
const pago = (extra) => ({
  fecha: '2026-10-05', descripcion: 'Pago de tu tarjeta (factura anterior)', monto: 300000, tipo: 'income', estado: 'faltante',
  fingerprint: 'fp-pago', categoria_sugerida: 'Pago de tarjeta', pago_tarjeta: true, pista: 'posible_traslado_propio',
  resumen_factura: RESUMEN, ...extra,
})
const respuesta = (item) => ({ ok: true, historial_id: 'h1', cuenta_id: 'c1', banco_detectado: 'nu', total_movimientos: 1, review: [item] })

describe('resumen de la factura anterior', () => {
  beforeEach(() => {
    Object.keys(api).forEach((k) => delete api[k])
    api.importarFaltantes = vi.fn().mockResolvedValue({ ok: true, importados: 1 })
  })

  it('el texto trae los tres importes', () => {
    const t = textoResumenFactura(RESUMEN).replace(/\s/g, ' ')
    expect(t).toMatch(/^Factura anterior: \$ ?500\.000 · Pagaste: \$ ?300\.000 · Quedó pendiente: \$ ?200\.000$/)
    expect(textoResumenFactura(null)).toBe('')
  })

  it('con salida igual en ahorros viene marcado; sin certeza queda apagado y fuera de «seleccionar todo»', () => {
    const encendido = normalizarPdf(respuesta(pago({ marcar_por_defecto: true })))
    const apagado = normalizarPdf(respuesta(pago({ marcar_por_defecto: false, aviso_linea: 'Parece el pago de tu tarjeta. Confirma el monto.' })))
    expect(clavesFaltantes([{ id: 'a', estado: 'listo', ...encendido }])).toEqual(['a:fp-pago'])
    expect(clavesFaltantes([{ id: 'a', estado: 'listo', ...apagado }])).toEqual([])
    expect(apagado.items[0]).toMatchObject({ resumen: RESUMEN, apagada: true })
  })

  it('la hoja muestra la tarjeta informativa y el aviso; la casilla del pago queda apagada y se puede encender', async () => {
    api.obtenerReviewExtracto = vi.fn().mockResolvedValue(respuesta(pago({
      marcar_por_defecto: false, aviso_linea: 'Parece el pago de tu tarjeta. Confirma el monto.' })))
    render(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} onCancelar={() => {}} />)
    const casilla = await screen.findByRole('checkbox', { name: /Importar Pago de tu tarjeta/ })
    expect(casilla).not.toBeChecked()
    expect(casilla).toBeEnabled()
    expect(screen.getByTestId('resumen-factura-anterior')).toHaveTextContent(/Factura anterior/)
    expect(screen.getByTestId('aviso-pago-factura')).toHaveTextContent('Parece el pago de tu tarjeta. Confirma el monto.')
  })
})
