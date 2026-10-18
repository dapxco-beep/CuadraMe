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

describe('aviso al borrar', () => {
  it('se agrega solo si el movimiento vino del correo o de un extracto', async () => {
    const { conAvisoDeBorrado, AVISO_NO_VUELVE } = await import('../lib/canales')
    expect(conAvisoDeBorrado('Base.', { origen: 'correo' })).toBe(`Base.\n\n${AVISO_NO_VUELVE}`)
    expect(conAvisoDeBorrado('Base.', [{ origen: 'manual', canales: ['manual', 'extracto'] }])).toContain('Descartados')
    expect(conAvisoDeBorrado('Base.', { origen: 'manual', canales: ['manual'] })).toBe('Base.')
    expect(AVISO_NO_VUELVE).toBe('Si lo borras, no lo volveremos a traer del correo. Podrás recuperarlo en Ver todo → Correos → Descartados.')
  })
})

describe('Recuperar todos', () => {
  const LISTA = [{ ...CORREO, id: 'a' }, { ...CORREO, id: 'b', comercio: 'OTRO' }, { ...CORREO, id: 'c', comercio: 'TERCERO' }]

  it('pide confirmar con el conteo y recupera todos (los que ya existen no se repiten)', async () => {
    api.correosDescartados = vi.fn().mockResolvedValue(LISTA)
    api.recuperarCorreo = vi.fn().mockImplementation((id) => Promise.resolve({ estado: id === 'c' ? 'ya_registrado' : 'pendiente' }))
    const onCambio = vi.fn()
    render(<CorreosDescartados cantidad={3} abierto onCambio={onCambio} />)
    const boton = await screen.findByTestId('recuperar-todos')
    expect(boton).toHaveTextContent('Recuperar todos (3)')
    // Sin el proveedor de diálogos no hay hoja de confirmación: ver el test del proveedor abajo.
    await userEvent.click(boton)
    await waitFor(() => expect(api.recuperarCorreo).toHaveBeenCalledTimes(3))
    expect(await screen.findByText(/Listo: 2 quedaron en «Por revisar» y 1 ya estaba registrado/)).toBeInTheDocument()
    expect(onCambio).toHaveBeenCalled()
  })

  it('con un solo correo no ofrece «Recuperar todos»', async () => {
    api.correosDescartados = vi.fn().mockResolvedValue([CORREO])
    render(<CorreosDescartados cantidad={1} abierto />)
    await screen.findByText('CAMARA DE COMERCIO DE BOGOTA')
    expect(screen.queryByTestId('recuperar-todos')).not.toBeInTheDocument()
  })
})

describe('Recuperar todos con confirmación', () => {
  it('si la persona cancela, no se recupera nada', async () => {
    vi.resetModules()
    vi.doMock('../lib/DialogosContext', () => ({ useDialogos: () => ({ confirmar: vi.fn().mockResolvedValue(false), avisar: vi.fn() }) }))
    const { default: Comp } = await import('../components/CorreosDescartados')
    api.correosDescartados = vi.fn().mockResolvedValue([{ ...CORREO, id: 'a' }, { ...CORREO, id: 'b' }])
    api.recuperarCorreo = vi.fn()
    render(<Comp cantidad={2} abierto />)
    await userEvent.click(await screen.findByTestId('recuperar-todos'))
    await new Promise((r) => setTimeout(r, 50))
    expect(api.recuperarCorreo).not.toHaveBeenCalled()
    vi.doUnmock('../lib/DialogosContext')
  })
})
