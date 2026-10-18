// Una línea del extracto con DOS montos («Pago $697.534,97 -$474.542,00»): no se marca ni se importa sin elegir el monto.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { render as renderBase, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Nu Colombia', tipo: 'ahorro' }], recargar: vi.fn() }),
}))

import SubidaMultiple from '../components/SubidaMultiple'
import { clavesFaltantes, leerMontoEscrito, montoDeLinea, normalizarPdf } from '../lib/subidaMultiple'

const render = (ui) => renderBase(<MemoryRouter>{ui}</MemoryRouter>)

const REVIEW = [
  {
    fecha: '2026-10-05', descripcion: 'Pago $697.534,97 -$474.542,00', monto: 222993, tipo: 'expense', estado: 'faltante', fingerprint: 'fp-dudosa',
    categoria_sugerida: 'Pago de tarjeta', lectura_dudosa: true, montos_alternativos: [697534.97, 474542], pago_tarjeta: true, pista: 'posible_traslado_propio',
  },
  { fecha: '2026-10-06', descripcion: 'Tienda de prueba', monto: 45000, tipo: 'expense', estado: 'faltante', fingerprint: 'fp-normal', categoria_sugerida: 'Otros' },
]
const RESPUESTA = {
  ok: true, historial_id: 'h1', cuenta_id: 'c1', banco_detectado: 'nu', total_movimientos: 2, review: REVIEW,
  origen: { titulo: 'Tarjeta Nu · corte 15 oct 2026', origen_texto: 'Correo «Llegó el extracto de tu tarjeta de crédito Nu» · archivo tarjeta_oct.pdf', cuenta_id: 'c1', cuenta_nombre: 'Nu Colombia' },
}

describe('lib: líneas de lectura dudosa', () => {
  it('normalizarPdf trae la marca y los montos; no entra en «seleccionar todo lo que falta»', () => {
    const base = normalizarPdf(RESPUESTA)
    const d = base.items.find((i) => i.k === 'fp-dudosa')
    expect(d).toMatchObject({ dudosa: true, montosAlt: [697534.97, 474542], pagoTarjeta: true, estado: 'nuevo' })
    expect(base.items.find((i) => i.k === 'fp-normal').dudosa).toBe(false)
    expect(base.origen.titulo).toBe('Tarjeta Nu · corte 15 oct 2026')
    expect(clavesFaltantes([{ id: 'a', estado: 'listo', ...base }])).toEqual(['a:fp-normal'])
  })
  it('el monto de la línea es el elegido; sin elegir, el leído', () => {
    const it = { dudosa: true, monto: 222993 }
    expect(montoDeLinea(it, 474542)).toBe(474542)
    expect(montoDeLinea(it, undefined)).toBe(222993)
    expect(montoDeLinea({ monto: 10 }, 99)).toBe(10)
  })
  it('lee lo que se escribe en el campo del monto', () => {
    expect(leerMontoEscrito('697.534,97')).toBe(697534.97)
    expect(leerMontoEscrito('$ 474.542,00')).toBe(474542)
    expect(leerMontoEscrito('474542')).toBe(474542)
    expect(leerMontoEscrito('474.542')).toBe(474542)
    expect(leerMontoEscrito('')).toBeNull()
    expect(leerMontoEscrito('abc')).toBeNull()
  })
})

describe('hoja de importar', () => {
  beforeEach(() => {
    Object.keys(api).forEach((k) => delete api[k])
    api.obtenerReviewExtracto = vi.fn().mockResolvedValue(RESPUESTA)
    api.importarFaltantes = vi.fn().mockResolvedValue({ ok: true, importados: 1 })
  })

  it('el encabezado dice qué extracto es, de dónde salió y a qué cuenta se importa', async () => {
    render(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} onCancelar={() => {}} onCambiarCuenta={() => {}} />)
    expect(await screen.findByText('Tarjeta Nu · corte 15 oct 2026')).toBeInTheDocument()
    expect(screen.getByText(/Llegó el extracto de tu tarjeta de crédito Nu/)).toBeInTheDocument()
    expect(screen.getByText('Nu Colombia', { selector: 'b' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Cambiar la cuenta de Tarjeta Nu/ })).toBeInTheDocument()
  })

  it('la línea de dos montos viene apagada, avisa y solo se importa con el monto elegido', async () => {
    render(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} onCancelar={() => {}} />)
    const casilla = await screen.findByRole('checkbox', { name: /Importar Pago \$697\.534,97/ })
    expect(casilla).not.toBeChecked()
    expect(casilla).toBeDisabled()
    expect(screen.getByText('Esta línea trae dos montos. Elige el correcto')).toBeInTheDocument()
    expect(screen.getByTestId('pista-pago-tarjeta')).toHaveTextContent(/traslado, no como gasto/)
    // Con la línea normal marcada, «Importar (1)» NO incluye la dudosa.
    expect(screen.getByRole('button', { name: 'Importar (1)' })).toBeEnabled()

    const montos = screen.getByRole('group', { name: 'Montos que trae la línea' })
    const botones = montos.querySelectorAll('button')
    expect(botones).toHaveLength(2)
    await userEvent.click(botones[1]) // $474.542
    expect(casilla).toBeChecked()
    expect(screen.getByText(/Se importará por \$\s?474\.542/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Importar (2)' }))
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalled())
    const [id, fps, , extra] = api.importarFaltantes.mock.calls[0]
    expect(id).toBe('h1')
    expect(fps.sort()).toEqual(['fp-dudosa', 'fp-normal'])
    expect(extra.montos).toEqual({ 'fp-dudosa': 474542 })
  })

  it('también se puede escribir el monto', async () => {
    render(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} onCancelar={() => {}} />)
    const campo = await screen.findByRole('textbox', { name: /Monto de Pago/ })
    await userEvent.type(campo, '300.000')
    expect(await screen.findByRole('button', { name: 'Importar (2)' })).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: 'Importar (2)' }))
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalled())
    expect(api.importarFaltantes.mock.calls[0][3].montos).toEqual({ 'fp-dudosa': 300000 })
  })

  it('sin elegir el monto, la línea no viaja', async () => {
    render(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} onCancelar={() => {}} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Importar (1)' }))
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalled())
    const [, fps, , extra] = api.importarFaltantes.mock.calls[0]
    expect(fps).toEqual(['fp-normal'])
    expect(extra.montos).toBeUndefined() // nada que elegir: no viaja ningún monto
  })
})
