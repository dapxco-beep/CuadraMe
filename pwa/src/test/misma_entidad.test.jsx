// Dos cuentas del MISMO banco (datos sintéticos): «Nu Colombia» (ahorro) y «Nu Tarjeta» (crédito).
// Los selectores dicen «Débito/Ahorros» / «Tarjeta de crédito», preguntan si es ambiguo y recuerdan la elección.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from './userEvent'

const CUENTAS = [
  { id: 'c1', nombre: 'Efectivo', saldo: 0, moneda: 'COP', tipo: 'efectivo', icono: '💵' },
  { id: 'a', nombre: 'Nu Colombia', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
  { id: 't', nombre: 'Nu Tarjeta', saldo: 0, moneda: 'COP', tipo: 'credito', icono: '💳' },
]

const api = vi.hoisted(() => ({ aprobarCorreo: vi.fn(), descartarCorreo: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ nombres: ['Otros'], iconoDe: () => '' }) }))

import CorreosPorRevisar from '../components/CorreosPorRevisar'
import {
  cuentaRecordada, etiquetaTipo, marcaDe, mismasDelBanco, productoDeTexto, recordarCuenta, textoOpcionCuenta,
} from '../lib/cuentasBanco'
import { sugerirCuenta } from '../lib/subidaMultiple'

const correo = (extra = {}) => ({
  id: 'k1', remitente: 'Nu <x@nu.com.co>', asunto: 'Compra aprobada', snippet: '', comercio: 'Tienda Uno', monto: 12000,
  categoria_sugerida: 'Otros', tipo_sugerido: 'expense', estado: 'pendiente', banco_detectado: 'Nu Colombia',
  cuenta_sugerida_id: null, falta_cuenta: false, falta_monto: false, preguntar_categoria: false,
  cuentas_candidatas: ['a', 't'], pregunta_cuenta: '¿Es la tarjeta de crédito (Nu Tarjeta) o la cuenta de ahorros/débito (Nu Colombia)?',
  producto_detectado: null, ...extra,
})

beforeEach(() => {
  localStorage.clear()
  api.aprobarCorreo.mockReset().mockResolvedValue({})
})

describe('utilidades de varias cuentas del mismo banco', () => {
  it('reconoce la marca y el tipo', () => {
    expect(marcaDe('Nu Tarjeta')).toEqual(['nu'])
    expect(marcaDe('Nu Colombia')).toEqual(['nu'])
    expect(etiquetaTipo(CUENTAS[1])).toBe('Débito/Ahorros')
    expect(etiquetaTipo(CUENTAS[2])).toBe('Tarjeta de crédito')
    expect(etiquetaTipo(CUENTAS[0])).toBe('')
    expect(mismasDelBanco(CUENTAS[1], CUENTAS).map((c) => c.id)).toEqual(['a', 't'])
  })

  it('solo agrega el tipo a la opción cuando el banco tiene varias cuentas', () => {
    expect(textoOpcionCuenta(CUENTAS[2], CUENTAS)).toBe('Nu Tarjeta · Tarjeta de crédito')
    expect(textoOpcionCuenta(CUENTAS[1], CUENTAS)).toBe('Nu Colombia · Débito/Ahorros')
    expect(textoOpcionCuenta(CUENTAS[0], CUENTAS)).toBe('Efectivo')
    expect(textoOpcionCuenta(CUENTAS[1], [CUENTAS[1]])).toBe('Nu Colombia')
  })

  it('deduce el producto del texto y recuerda la elección por banco + tipo', () => {
    expect(productoDeTexto('extracto tarjeta de crédito, pago mínimo')).toBe('credito')
    expect(productoDeTexto('extracto cuenta de ahorros')).toBe('debito')
    expect(productoDeTexto('extracto septiembre')).toBe(null)
    recordarCuenta('Nu Colombia', 'credito', 't')
    expect(cuentaRecordada('Nu Colombia', 'credito', CUENTAS)).toBe('t')
    expect(cuentaRecordada('Nu Colombia', 'debito', CUENTAS)).toBe('')
    expect(cuentaRecordada('Nu Colombia', 'credito', [CUENTAS[0]])).toBe('') // la cuenta ya no existe
  })

  it('subir extractos: el nombre del archivo desempata entre cuentas del mismo banco', () => {
    expect(sugerirCuenta('extracto_nu_tarjeta_credito.pdf', CUENTAS, 'c1')).toBe('t')
    expect(sugerirCuenta('extracto_nu_ahorros_sep.pdf', CUENTAS, 'c1')).toBe('a')
    expect(sugerirCuenta('extracto_nu_sep.pdf', CUENTAS, 'c1')).toBe('c1') // ambiguo: no adivina
    recordarCuenta('Nu Colombia', null, 'a')
    expect(sugerirCuenta('extracto_nu_sep.pdf', CUENTAS, 'c1')).toBe('a') // lo que la persona eligió antes
  })
})

describe('aprobar correos de un banco con dos cuentas', () => {
  it('pregunta en lenguaje simple y muestra los tipos en las opciones', async () => {
    render(<CorreosPorRevisar correos={[correo()]} onResuelto={vi.fn()} />)
    expect(screen.getByTestId('pregunta-cuenta')).toHaveTextContent(/¿Es la tarjeta de crédito \(Nu Tarjeta\)/)
    expect(screen.getByRole('option', { name: 'Nu Tarjeta · Tarjeta de crédito' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Nu Colombia · Débito/Ahorros' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Aprobar/ })).toBeDisabled() // no se asume ninguna cuenta
  })

  it('al elegir la tarjeta aprueba con esa cuenta y la recuerda para la próxima', async () => {
    const { unmount } = render(<CorreosPorRevisar correos={[correo()]} onResuelto={vi.fn()} />)
    await userEvent.selectOptions(screen.getByLabelText('Cuenta de Tienda Uno'), 't')
    expect(screen.queryByTestId('pregunta-cuenta')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /Aprobar/ }))
    expect(api.aprobarCorreo).toHaveBeenCalledWith('k1', 't')
    unmount()

    // Otro correo del mismo banco y tipo (producto no detectado): ya viene con la tarjeta elegida.
    render(<CorreosPorRevisar correos={[correo({ id: 'k2' })]} onResuelto={vi.fn()} />)
    expect(screen.getByLabelText('Cuenta de Tienda Uno')).toHaveValue('t')
    expect(screen.getByRole('button', { name: /Aprobar/ })).toBeEnabled()
  })

  it('con cuenta sugerida por el servidor no pregunta', () => {
    render(<CorreosPorRevisar correos={[correo({ cuenta_sugerida_id: 't', cuentas_candidatas: [], pregunta_cuenta: null, producto_detectado: 'credito' })]} onResuelto={vi.fn()} />)
    expect(screen.queryByTestId('pregunta-cuenta')).toBeNull()
    expect(screen.getByLabelText('Cuenta de Tienda Uno')).toHaveValue('t')
  })
})
