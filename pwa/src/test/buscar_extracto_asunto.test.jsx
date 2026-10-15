// «¿No ves un extracto?»: búsqueda por asunto. Datos inventados.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const api = vi.hoisted(() => ({ buscarExtractosPorAsunto: vi.fn(), procesarExtractosPorAsunto: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))

import BuscarExtractoPorAsunto from '../components/BuscarExtractoPorAsunto'

const HALLADOS = [
  { gmail_msg_id: 'm1', remitente: 'Nu <nu@nu.com.co>', asunto: 'Llegó el extracto de tu tarjeta de crédito Nu', fecha: '2026-10-05T10:00:00', archivos: ['a.pdf'], ya_en_lista: false },
  { gmail_msg_id: 'm2', remitente: 'Nu <nu@nu.com.co>', asunto: 'Llegó el extracto de tu tarjeta de crédito Nu', fecha: '2026-09-05T10:00:00', archivos: ['b.pdf'], ya_en_lista: true },
]

describe('BuscarExtractoPorAsunto', () => {
  beforeEach(() => {
    Object.values(api).forEach((f) => f.mockReset())
  })

  it('busca, lista, y agrega solo los elegidos que no estaban', async () => {
    api.buscarExtractosPorAsunto.mockResolvedValue(HALLADOS)
    api.procesarExtractosPorAsunto.mockResolvedValue({ ok: true, extractos_nuevos: 1 })
    const onAgregado = vi.fn()
    render(<BuscarExtractoPorAsunto onAgregado={onAgregado} />)
    const boton = screen.getByRole('button', { name: /buscar/i })
    expect(boton).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/no ves un extracto/i), { target: { value: 'Llegó el extracto de tu tarjeta' } })
    fireEvent.click(boton)
    await waitFor(() => expect(api.buscarExtractosPorAsunto).toHaveBeenCalledWith('Llegó el extracto de tu tarjeta'))
    expect(await screen.findByText('Ya está en tu lista')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /agregar 1/i }))
    await waitFor(() => expect(api.procesarExtractosPorAsunto).toHaveBeenCalledWith(['m1']))
    expect(await screen.findByText(/1 extracto agregado/)).toBeTruthy()
    expect(onAgregado).toHaveBeenCalled()
  })

  it('sin resultados lo dice y un error se muestra en llano', async () => {
    api.buscarExtractosPorAsunto.mockResolvedValueOnce([])
    render(<BuscarExtractoPorAsunto />)
    fireEvent.change(screen.getByLabelText(/no ves un extracto/i), { target: { value: 'xyz abc' } })
    fireEvent.click(screen.getByRole('button', { name: /buscar/i }))
    expect(await screen.findByText(/No encontré correos/)).toBeTruthy()
    api.buscarExtractosPorAsunto.mockRejectedValueOnce(new Error('Gmail no está conectado'))
    fireEvent.click(screen.getByRole('button', { name: /buscar/i }))
    expect(await screen.findByRole('alert')).toBeTruthy()
  })
})
