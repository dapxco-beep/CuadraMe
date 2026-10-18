import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../lib/api', () => ({
  api: {
    vistaReglaCorreo: vi.fn(),
    crearReglaCorreo: vi.fn(),
    aplicarReglaCorreoAnteriores: vi.fn(),
    reglasCorreo: vi.fn(),
    borrarReglaCorreo: vi.fn(),
    buscarExtractosPorAsunto: vi.fn(),
    procesarExtractosPorAsunto: vi.fn(),
  },
}))

import { api } from '../lib/api'
import HojaEnsenarCorreo from '../components/HojaEnsenarCorreo'
import MisReglasCorreo, { describirRegla } from '../components/MisReglasCorreo'
import BuscarExtractoPorAsunto from '../components/BuscarExtractoPorAsunto'
import { montosDelTexto, nombreDelRango, palabrasDelTexto, tocarPalabra } from '../lib/ensenarCorreo'

const TEXTO = 'Pagaste con tu Cuenta de ahorros Nu Hola Daniel: Pagaste en: ICETEX. La cantidad de: $1.000.000,00. Más el impuesto del 4xmil de: $0,00.'

beforeEach(() => vi.clearAllMocks())

describe('ayudas de «Enseñar a leer»', () => {
  it('lista las cifras con lo que las antecede y descarta números sueltos', () => {
    const m = montosDelTexto(TEXTO)
    expect(m.map((x) => x.texto)).toEqual(['$1.000.000,00', '$0,00'])
    expect(m[0].contexto).toBe('La cantidad de:')
    expect(montosDelTexto('Tienes 2 avisos')).toEqual([])
  })

  it('arma el nombre con el rango de palabras tocadas, en cualquier orden', () => {
    const p = palabrasDelTexto('Pagaste en: Colegio San José. La cantidad')
    expect(nombreDelRango(p, { a: 2, b: 4 })).toBe('Colegio San José')
    expect(nombreDelRango(p, { a: 4, b: 2 })).toBe('Colegio San José')
    expect(nombreDelRango(p, null)).toBe('')
  })

  it('el segundo toque extiende, tocar la misma palabra la suelta, el tercero empieza de nuevo', () => {
    let r = tocarPalabra(null, 3)
    expect(r).toEqual({ a: 3, b: 3 })
    r = tocarPalabra(r, 5)
    expect(r).toEqual({ a: 3, b: 5 })
    expect(tocarPalabra(r, 7)).toEqual({ a: 7, b: 7 })
    expect(tocarPalabra({ a: 3, b: 3 }, 3)).toBeNull()
  })
})

describe('hoja «Enseñar a leer»', () => {
  const vista = { gmail_msg_id: 'nu1', asunto: 'Pagaste con tu Cuenta de ahorros Nu', remitente: 'Nu <nu@nu.com.co>', texto: TEXTO, monto_actual: 0, comercio_actual: 'Gasto sin detalle', tipo_actual: 'expense' }

  it('marca monto, nombre y tipo, guarda y pasa los parecidos a Por revisar tras confirmar', async () => {
    api.vistaReglaCorreo.mockResolvedValue(vista)
    api.crearReglaCorreo.mockResolvedValue({ regla: { id: 'r1' }, correo: { id: 'c1', monto: 1000000, comercio: 'Icetex', tipo: 'expense', estado: 'pendiente' }, similares: 3 })
    api.aplicarReglaCorreoAnteriores.mockResolvedValue({ ok: true, recuperados: 3 })
    const onListo = vi.fn()
    render(<HojaEnsenarCorreo correoId="c1" onCerrar={() => {}} onListo={onListo} />)
    await screen.findByText('¿Cuál es el monto?')
    expect(api.vistaReglaCorreo).toHaveBeenCalledWith({ correo_id: 'c1' })
    fireEvent.click(screen.getByText('$1.000.000,00'))
    await screen.findByText('¿A quién o dónde fue?')
    fireEvent.click(screen.getByText('ICETEX.'))
    fireEvent.click(screen.getByText('Seguir'))
    await screen.findByText('¿Fue un gasto o un ingreso?')
    fireEvent.click(screen.getByText('Guardar'))
    await screen.findByText(/Encontré 3 correos parecidos/)
    expect(api.crearReglaCorreo).toHaveBeenCalledWith({ correo_id: 'c1', monto_texto: '$1.000.000,00', comercio_texto: 'ICETEX', tipo: 'expense' })
    expect(api.aplicarReglaCorreoAnteriores).not.toHaveBeenCalled() // pregunta antes de mover nada
    fireEvent.click(screen.getByText('Pasar a Por revisar'))
    await screen.findByText(/Pasé 3 correos a «Por revisar»/)
    expect(api.aplicarReglaCorreoAnteriores).toHaveBeenCalledWith('r1')
    expect(onListo).toHaveBeenCalledWith(expect.objectContaining({ recuperados: 3 }))
  })

  it('sin parecidos termina directo y «Ahora no» no mueve nada', async () => {
    api.vistaReglaCorreo.mockResolvedValue(vista)
    api.crearReglaCorreo.mockResolvedValue({ regla: { id: 'r1' }, correo: null, similares: 0 })
    render(<HojaEnsenarCorreo gmailMsgId="nu1" onCerrar={() => {}} />)
    await screen.findByText('¿Cuál es el monto?')
    expect(api.vistaReglaCorreo).toHaveBeenCalledWith({ gmail_msg_id: 'nu1' })
    fireEvent.click(screen.getByText('$1.000.000,00'))
    await screen.findByText('¿A quién o dónde fue?')
    fireEvent.click(screen.getByText('Saltar este paso'))
    await screen.findByText('¿Fue un gasto o un ingreso?')
    fireEvent.click(screen.getByText('Ingreso'))
    fireEvent.click(screen.getByText('Guardar'))
    await screen.findByText(/Cuando llegue un correo así, lo leo solo/)
    expect(api.crearReglaCorreo).toHaveBeenCalledWith({ gmail_msg_id: 'nu1', monto_texto: '$1.000.000,00', comercio_texto: null, tipo: 'income' })
    expect(api.aplicarReglaCorreoAnteriores).not.toHaveBeenCalled()
  })

  it('muestra el error del servidor y deja volver a intentar', async () => {
    api.vistaReglaCorreo.mockResolvedValue(vista)
    api.crearReglaCorreo.mockRejectedValue(new Error('No pudimos aprender dónde está el monto.'))
    render(<HojaEnsenarCorreo gmailMsgId="nu1" onCerrar={() => {}} />)
    await screen.findByText('¿Cuál es el monto?')
    fireEvent.click(screen.getByText('$0,00'))
    await screen.findByText('¿A quién o dónde fue?')
    fireEvent.click(screen.getByText('Saltar este paso'))
    fireEvent.click(await screen.findByText('Guardar'))
    await screen.findByRole('alert')
    expect(screen.getByText('Guardar')).not.toBeDisabled()
  })
})

describe('«Mis reglas de correo»', () => {
  it('lista, pide confirmar y borra', async () => {
    const r = { id: 'r1', remitente_dominio: 'nu.com.co', esqueleto_asunto: 'pagaste con tu cuenta de ahorros nu', tipo: 'expense', marca_monto: true, marca_comercio: true, usos: 2 }
    api.reglasCorreo.mockResolvedValue([r])
    api.borrarReglaCorreo.mockResolvedValue({ ok: true })
    render(<MisReglasCorreo />)
    await screen.findByText('pagaste con tu cuenta de ahorros nu')
    expect(describirRegla(r)).toBe('Lee el monto y el nombre como gasto')
    fireEvent.click(screen.getByRole('button', { name: /Borrar la regla/ }))
    expect(api.borrarReglaCorreo).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Sí, borrar'))
    await waitFor(() => expect(api.borrarReglaCorreo).toHaveBeenCalledWith('r1'))
    await screen.findByText(/Aún no le has enseñado ninguno/)
  })

  it('sin reglas explica cómo crear la primera', async () => {
    api.reglasCorreo.mockResolvedValue([])
    render(<MisReglasCorreo />)
    await screen.findByText(/Aún no le has enseñado ninguno/)
  })
})

describe('desde «Buscar un movimiento por su asunto»', () => {
  it('cada resultado ofrece «Enseñarle a leer este correo» y abre la hoja con ese mensaje', async () => {
    api.buscarExtractosPorAsunto.mockResolvedValue([
      { gmail_msg_id: 'ix1', remitente: 'Nu <nu@nu.com.co>', asunto: 'Pagaste con tu Cuenta de ahorros Nu', fecha: '2026-09-28T10:00:00', archivos: [], ya_en_lista: false },
    ])
    api.vistaReglaCorreo.mockResolvedValue({ gmail_msg_id: 'ix1', asunto: 'x', remitente: 'y', texto: TEXTO, monto_actual: 0, comercio_actual: '', tipo_actual: 'expense' })
    render(<BuscarExtractoPorAsunto modo="movimiento" onAgregado={() => {}} />)
    fireEvent.change(screen.getByLabelText('¿Falta un movimiento?'), { target: { value: 'Pagaste con tu Cuenta' } })
    fireEvent.click(screen.getByText('Buscar'))
    fireEvent.click(await screen.findByText('Enseñarle a leer este correo'))
    await screen.findByText('¿Cuál es el monto?')
    expect(api.vistaReglaCorreo).toHaveBeenCalledWith({ gmail_msg_id: 'ix1' })
  })

  it('en modo extracto no aparece el botón', async () => {
    api.buscarExtractosPorAsunto.mockResolvedValue([
      { gmail_msg_id: 'ex1', remitente: 'Banco <b@banco.com>', asunto: 'Llegó tu extracto', fecha: '2026-09-28T10:00:00', archivos: ['e.pdf'], ya_en_lista: false },
    ])
    render(<BuscarExtractoPorAsunto onAgregado={() => {}} />)
    fireEvent.change(screen.getByLabelText('¿No ves un extracto?'), { target: { value: 'Llegó tu extracto' } })
    fireEvent.click(screen.getByText('Buscar'))
    await screen.findByText('Llegó tu extracto')
    expect(screen.queryByText('Enseñarle a leer este correo')).toBeNull()
  })
})
