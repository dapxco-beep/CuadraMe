import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../lib/api', () => ({
  api: {
    buscarExtractosPorAsunto: vi.fn(),
    procesarExtractosPorAsunto: vi.fn(),
    sincronizarCorreos: vi.fn(),
  },
}))

import { api } from '../lib/api'
import BuscarExtractoPorAsunto, { textoAgregadoMov } from '../components/BuscarExtractoPorAsunto'
import { sincronizarTodo } from '../lib/sincronizarGmail'

beforeEach(() => vi.clearAllMocks())

describe('buscar un movimiento por asunto', () => {
  it('busca en modo movimiento, lista el correo sin PDF y lo agrega a Por revisar', async () => {
    api.buscarExtractosPorAsunto.mockResolvedValue([
      { gmail_msg_id: 'ix1', remitente: 'Nu <nu@nu.com.co>', asunto: 'Pagaste con tu Cuenta de ahorros Nu', fecha: '2026-09-28T10:00:00', archivos: [], ya_en_lista: false },
    ])
    api.procesarExtractosPorAsunto.mockResolvedValue({ ok: true, movimientos_nuevos: 1 })
    render(<BuscarExtractoPorAsunto modo="movimiento" onAgregado={() => {}} />)
    fireEvent.change(screen.getByLabelText('¿Falta un movimiento?'), { target: { value: 'Pagaste con tu Cuenta' } })
    fireEvent.click(screen.getByText('Buscar'))
    await screen.findByText('Pagaste con tu Cuenta de ahorros Nu')
    expect(api.buscarExtractosPorAsunto).toHaveBeenCalledWith('Pagaste con tu Cuenta', 'movimiento')
    fireEvent.click(screen.getByText(/Agregar 1 a Por revisar/))
    await screen.findByText(/1 movimiento en «Por revisar»/)
    expect(api.procesarExtractosPorAsunto).toHaveBeenCalledWith(['ix1'], 'movimiento')
  })

  it('textos del resultado', () => {
    expect(textoAgregadoMov({ movimientos_nuevos: 2 })).toMatch(/2 movimientos/)
    expect(textoAgregadoMov({ descartados: 1 })).toMatch(/no parece un movimiento/)
    expect(textoAgregadoMov({})).toMatch(/ya estaba registrado/)
  })

  it('«Releer los últimos 60 días» pide ventana larga solo en la primera llamada', async () => {
    api.sincronizarCorreos
      .mockResolvedValueOnce({ ok: true, completado: false, leidos: 40, total_estimado: 80 })
      .mockResolvedValueOnce({ ok: true, completado: true, leidos: 80, total_estimado: 80 })
    await sincronizarTodo({ completa: true, tipo: 'movimientos', dias: 60, releer: true })
    expect(api.sincronizarCorreos.mock.calls[0][0]).toEqual({ completa: true, dias: 60, releer: true, tipo: 'movimientos' })
    expect(api.sincronizarCorreos.mock.calls[1][0]).toEqual({ tipo: 'movimientos' })
  })
})
