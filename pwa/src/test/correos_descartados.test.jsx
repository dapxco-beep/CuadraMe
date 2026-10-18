// «Correos descartados»: se listan con fecha, comercio, monto y motivo, y «Recuperar» los devuelve a «Por revisar».
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import CorreosDescartados from '../components/CorreosDescartados'

const CORREO = {
  id: 'k1', comercio: 'CAMARA DE COMERCIO DE BOGOTA', monto: 390500, moneda: 'COP', estado: 'descartado',
  fecha_movimiento: '2026-10-06T14:30:00', fecha_movimiento_con_hora: true,
  motivo_descarte: 'Se parecía a un movimiento que borraste',
}

beforeEach(() => {
  Object.keys(api).forEach((k) => delete api[k])
})

describe('Correos descartados', () => {
  it('no se muestra si no hay ninguno', () => {
    const { container } = render(<CorreosDescartados cantidad={0} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('lista los correos con su motivo y los recupera', async () => {
    api.correosDescartados = vi.fn().mockResolvedValue([CORREO])
    api.recuperarCorreo = vi.fn().mockResolvedValue({ ...CORREO, estado: 'pendiente' })
    const onCambio = vi.fn()
    render(<CorreosDescartados cantidad={1} onCambio={onCambio} />)
    await userEvent.click(screen.getByRole('button', { name: /Correos descartados \(1\)/ }))
    expect(await screen.findByText(/Los descartaste al borrar un movimiento parecido, o no eran una compra/)).toBeInTheDocument()
    expect(screen.getByText('CAMARA DE COMERCIO DE BOGOTA')).toBeInTheDocument()
    expect(screen.getByText(/Se parecía a un movimiento que borraste/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Recuperar/ }))
    await waitFor(() => expect(api.recuperarCorreo).toHaveBeenCalledWith('k1'))
    expect(await screen.findByText(/lo encuentras en «Por revisar»/)).toBeInTheDocument()
    expect(onCambio).toHaveBeenCalled()
    expect(screen.queryByText('CAMARA DE COMERCIO DE BOGOTA')).not.toBeInTheDocument()
  })

  it('si ya existe el movimiento, lo dice y no lo manda a Por revisar', async () => {
    api.correosDescartados = vi.fn().mockResolvedValue([CORREO])
    api.recuperarCorreo = vi.fn().mockResolvedValue({ ...CORREO, estado: 'ya_registrado' })
    render(<CorreosDescartados cantidad={1} abierto />)
    await userEvent.click(await screen.findByRole('button', { name: /Recuperar/ }))
    expect(await screen.findByText(/Ya tenías ese movimiento registrado/)).toBeInTheDocument()
  })
})
