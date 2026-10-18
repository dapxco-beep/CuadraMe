// «Arreglar mis extractos de la tarjeta»: textos, botón único, vista previa, avance, resultado y «Revisar e importar».
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({ previaArreglarTarjetas: vi.fn(), arreglarTarjetas: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({ useCuentas: () => ({ cuentas: [], recargar: vi.fn().mockResolvedValue() }) }))

import ArreglarTarjetas from '../components/ArreglarTarjetas'
import {
  avisoExtracto, juntarResultados, lineaExtracto, lineaResultado, resumenFinal, textoBoton, textoProgreso, textoSaldo,
} from '../lib/arreglarTarjetas'

const fmt = (n) => `$${n}`
const EXT = (mes, extra = {}) => ({
  historial_id: `h-${mes}`, mes, cuenta_actual: { id: 'nu', nombre: 'Nu Colombia' },
  cuenta_destino: { id: 'tj', nombre: 'Nu Colombia Crédito' }, movera: 2, releera: true, puede_releerse: true, requiere_clave: false, ...extra,
})
const PREVIA = {
  total: 2, total_tarjeta: 2, extractos: [EXT('2026-07'), EXT('2026-08', { movera: 18 })],
  saldos: {
    por_cuenta: [
      { id: 'nu', nombre: 'Nu Colombia', saldo_antes: 880000, saldo_despues: 1000000 },
      { id: 'tj', nombre: 'Nu Colombia Crédito', saldo_antes: -300000, saldo_despues: -420000 },
    ],
    total_antes: 580000, total_despues: 580000,
  },
}
const PASO = (mes, extra = {}) => ({
  restantes: 0,
  resultados: [{
    historial_id: `h-${mes}`, mes, estado: 'arreglado', movidos: 2, nuevas: 1, lineas_leidas: 3, lectura_completa: true,
    mensaje_lectura: 'Leí 3 líneas y suman lo que dice tu extracto ✓', motivo: null, ...extra,
  }],
})

function montar(props = {}) {
  return render(<MemoryRouter><ArreglarTarjetas {...props} /></MemoryRouter>)
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  api.previaArreglarTarjetas.mockResolvedValue(PREVIA)
})

describe('textos', () => {
  it('botón, línea por extracto y avisos', () => {
    expect(textoBoton(6)).toBe('Arreglar mis extractos de la tarjeta (6)')
    expect(lineaExtracto(EXT('2026-07'))).toBe('Julio 2026 · pasa de Nu Colombia a Nu Colombia Crédito · 2 movimientos')
    expect(lineaExtracto(EXT('2026-07', { movera: 1 }))).toContain('1 movimiento')
    expect(lineaExtracto(EXT('2026-07', { cuenta_destino: null, movera: 0 }))).toBe('Julio 2026 · lo leo otra vez con el lector de hoy')
    expect(avisoExtracto(EXT('2026-07', { requiere_clave: true }))).toContain('clave de tu PDF')
    expect(avisoExtracto(EXT('2026-07', { puede_releerse: false }))).toContain('Conecta Gmail')
    expect(avisoExtracto(EXT('2026-07'))).toBe('')
  })

  it('saldos, progreso y resumen', () => {
    expect(textoSaldo(PREVIA.saldos.por_cuenta[0], fmt)).toBe('Nu Colombia: de $880000 a $1000000')
    expect(textoProgreso(3, 6)).toBe('Arreglando 3 de 6…')
    expect(resumenFinal({ arreglados: 6, movidos: 36, por_importar: 41 })).toBe(
      'Arreglé 6 extractos: moví 36 movimientos a tu tarjeta, encontré 41 compras por importar.')
    expect(resumenFinal({ arreglados: 0, saltados: 0 })).toBe('Tus extractos de la tarjeta ya estaban bien. No cambié nada.')
    expect(resumenFinal({ arreglados: 1, movidos: 1, por_importar: 1, saltados: 1 })).toBe(
      'Arreglé 1 extracto: moví 1 movimiento a tu tarjeta, encontré 1 compra por importar. 1 extracto quedó para después.')
  })

  it('junta los pasos y cuenta saltados', () => {
    const saltado = PASO('2026-08', { estado: 'saltado', movidos: 0, nuevas: 0, motivo: 'No pudimos releerlo ahora.' })
    const j = juntarResultados([PASO('2026-07'), saltado])
    expect(j).toMatchObject({ arreglados: 1, saltados: 1, movidos: 2, por_importar: 1 })
    expect(lineaResultado(j.resultados[0])).toBe(
      'Julio 2026: Leí 3 líneas y suman lo que dice tu extracto ✓ · Moví 2 movimientos · 1 compra nueva por importar')
    expect(lineaResultado(j.resultados[1])).toBe('Agosto 2026: para después. No pudimos releerlo ahora.')
  })
})

describe('<ArreglarTarjetas>', () => {
  it('sin nada que arreglar no dibuja nada', async () => {
    api.previaArreglarTarjetas.mockResolvedValue({ total: 0, extractos: [], saldos: { por_cuenta: [] } })
    const { container } = montar()
    await waitFor(() => expect(api.previaArreglarTarjetas).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('si la previa falla no molesta', async () => {
    api.previaArreglarTarjetas.mockRejectedValue(new Error('x'))
    const { container } = montar()
    await waitFor(() => expect(api.previaArreglarTarjetas).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('un botón abre la previa con la lista y los saldos; nada cambia hasta confirmar', async () => {
    montar()
    await userEvent.click(await screen.findByRole('button', { name: /Arreglar mis extractos de la tarjeta \(2\)/ }))
    expect(screen.getByText('Julio 2026 · pasa de Nu Colombia a Nu Colombia Crédito · 2 movimientos')).toBeInTheDocument()
    expect(screen.getByText('Agosto 2026 · pasa de Nu Colombia a Nu Colombia Crédito · 18 movimientos')).toBeInTheDocument()
    expect(screen.getByTestId('saldos-arreglar')).toHaveTextContent('Nu Colombia Crédito: de')
    expect(api.arreglarTarjetas).not.toHaveBeenCalled()
  })

  it('arregla de a uno con avance, muestra el resumen y «Revisar e importar»', async () => {
    const onRevisar = vi.fn()
    const onListo = vi.fn()
    let liberar
    api.arreglarTarjetas
      .mockImplementationOnce(() => new Promise((res) => { liberar = () => res(PASO('2026-07')) }))
      .mockResolvedValueOnce(PASO('2026-08'))
    montar({ onRevisar, onListo })
    await userEvent.click(await screen.findByTestId('arreglar-tarjetas'))
    await userEvent.click(screen.getByRole('button', { name: 'Sí, arreglar todo' }))
    expect(await screen.findByTestId('progreso-arreglar')).toHaveTextContent('Arreglando 1 de 2…')
    liberar()
    expect(await screen.findByTestId('resumen-arreglar')).toHaveTextContent(
      'Arreglé 2 extractos: moví 4 movimientos a tu tarjeta, encontré 2 compras por importar.')
    expect(api.arreglarTarjetas).toHaveBeenNthCalledWith(1, { maximo: 1, excluir: [], continuar: false })
    expect(api.arreglarTarjetas).toHaveBeenNthCalledWith(2, { maximo: 1, excluir: ['h-2026-07'], continuar: true })
    expect(onListo).toHaveBeenCalled()
    await userEvent.click(screen.getByTestId('revisar-importar'))
    expect(onRevisar).toHaveBeenCalled()
  })

  it('un extracto saltado se dice y sin compras nuevas no hay «Revisar e importar»', async () => {
    api.arreglarTarjetas
      .mockResolvedValueOnce(PASO('2026-07', { nuevas: 0 }))
      .mockResolvedValueOnce(PASO('2026-08', { estado: 'saltado', movidos: 0, nuevas: 0, motivo: 'No pudimos abrir el PDF. No cambié nada.' }))
    montar()
    await userEvent.click(await screen.findByTestId('arreglar-tarjetas'))
    await userEvent.click(screen.getByRole('button', { name: 'Sí, arreglar todo' }))
    expect(await screen.findByTestId('resumen-arreglar')).toHaveTextContent('1 extracto quedó para después')
    expect(screen.getByText(/Agosto 2026: para después\. No pudimos abrir el PDF/)).toBeInTheDocument()
    expect(screen.queryByTestId('revisar-importar')).toBeNull()
  })

  it('si falla a la mitad dice lo que sí quedó hecho', async () => {
    api.arreglarTarjetas.mockResolvedValueOnce(PASO('2026-07')).mockRejectedValueOnce(new Error('Failed to fetch'))
    montar()
    await userEvent.click(await screen.findByTestId('arreglar-tarjetas'))
    await userEvent.click(screen.getByRole('button', { name: 'Sí, arreglar todo' }))
    expect(await screen.findByTestId('resumen-arreglar')).toHaveTextContent('Arreglé 1 extracto')
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})
