// Buzón de opinión: pantalla «Tu opinión cuenta», panel del administrador y puntos de entrada.
// Datos sintéticos; la API se reemplaza.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const api = vi.hoisted(() => ({
  enviarComentario: vi.fn(),
  misComentarios: vi.fn(),
  comentariosAdmin: vi.fn(),
  cambiarComentario: vi.fn(),
  marcarComentariosVistos: vi.fn(),
  exportarComentariosCSV: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
const avisar = vi.hoisted(() => vi.fn())
vi.mock('../lib/DialogosContext', () => ({ useDialogos: () => ({ avisar, confirmar: vi.fn() }) }))

import Opinion from '../screens/Opinion'
import ComentariosAdmin from '../screens/ComentariosAdmin'
import ErrorAmable from '../brand/ErrorAmable'
import { limpiarDesde, resumenDispositivo, tipoInicial } from '../lib/opinion'

const montar = (ui, ruta = '/opinion') =>
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/opinion" element={ui} />
        <Route path="/comentarios-admin" element={ui} />
        <Route path="*" element={<p>otra</p>} />
      </Routes>
    </MemoryRouter>
  )

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  avisar.mockReset()
  api.misComentarios.mockResolvedValue([])
})

describe('Utilidades de opinión', () => {
  it('solo acepta tipos conocidos y deja la ruta sin parámetros', () => {
    expect(tipoInicial('problema')).toBe('problema')
    expect(tipoInicial('<script>')).toBe('sugerencia')
    expect(limpiarDesde('/movimientos?mes=2026-01&saldo=999')).toBe('/movimientos')
    expect(limpiarDesde('https://malo.com')).toBe('')
    expect(limpiarDesde('/a'.repeat(100))).toBe('')
  })

  it('el resumen del dispositivo es corto y sin datos sensibles', () => {
    const r = resumenDispositivo()
    expect(r.length).toBeLessThan(60)
    expect(r).toMatch(/móvil|escritorio/)
  })
})

describe('Pantalla «Tu opinión cuenta»', () => {
  it('envía el tipo elegido, el mensaje, la pantalla de origen y el dispositivo; muestra gracias', async () => {
    api.enviarComentario.mockResolvedValue({ ok: true, id: 'c1' })
    montar(<Opinion />, '/opinion?tipo=problema&desde=/movimientos?mes=2026-01')
    expect(screen.getByRole('radio', { name: /Algo falló/ })).toHaveAttribute('aria-checked', 'true')
    const enviar = screen.getByRole('button', { name: 'Enviar' })
    expect(enviar).toBeDisabled() // vacío
    fireEvent.change(screen.getByLabelText('Tu mensaje'), { target: { value: 'Se cierra al subir el PDF' } })
    expect(screen.getByText('25/2000')).toBeInTheDocument() // contador
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(enviar)
    await waitFor(() => expect(api.enviarComentario).toHaveBeenCalledTimes(1))
    const cuerpo = api.enviarComentario.mock.calls[0][0]
    expect(cuerpo).toMatchObject({
      tipo: 'problema', mensaje: 'Se cierra al subir el PDF', pantalla: '/movimientos', puede_contactar: false,
    })
    expect(cuerpo.dispositivo).toMatch(/móvil|escritorio/)
    expect(Object.keys(cuerpo).sort()).toEqual(
      ['dispositivo', 'mensaje', 'pantalla', 'puede_contactar', 'tipo', 'version_app']
    ) // nada financiero
    expect(await screen.findByTestId('opinion-gracias')).toBeInTheDocument()
    expect(avisar).toHaveBeenCalled()
  })

  it('si falla el envío conserva el texto y muestra el error amable', async () => {
    api.enviarComentario.mockRejectedValue(new Error('Ya nos escribiste varias veces seguidas, gracias.'))
    montar(<Opinion />)
    fireEvent.change(screen.getByLabelText('Tu mensaje'), { target: { value: 'Una idea' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    expect(await screen.findByText(/Ya nos escribiste/)).toBeInTheDocument()
    expect(screen.getByLabelText('Tu mensaje')).toHaveValue('Una idea')
    expect(screen.queryByTestId('opinion-gracias')).toBeNull()
  })

  it('lista «Tus comentarios» con su estado en palabras llanas y la respuesta', async () => {
    api.misComentarios.mockResolvedValue([
      { id: 'a', tipo: 'sugerencia', mensaje: 'Idea uno', creado_en: '2026-10-01T10:00:00', estado: 'Ya lo resolvimos', respuesta: 'Ya quedó' },
      { id: 'b', tipo: 'pregunta', mensaje: 'Duda dos', creado_en: '2026-10-02T10:00:00', estado: 'Recibido', respuesta: null },
    ])
    montar(<Opinion />)
    const lista = await screen.findByTestId('mis-comentarios')
    expect(within(lista).getByText('Ya lo resolvimos')).toBeInTheDocument()
    expect(within(lista).getByText(/Ya quedó/)).toBeInTheDocument()
    expect(within(lista).getByText('Recibido')).toBeInTheDocument()
  })
})

describe('«Cuéntanos qué pasó» en errores amables', () => {
  it('lleva a /opinion como problema con la pantalla de origen; sin la prop no aparece', () => {
    window.location.hash = '#/movimientos?x=1'
    const { rerender } = render(<ErrorAmable reportar />)
    const enlace = screen.getByRole('link', { name: 'Cuéntanos qué pasó' })
    expect(enlace.getAttribute('href')).toBe('#/opinion?tipo=problema&desde=%2Fmovimientos')
    rerender(<ErrorAmable />)
    expect(screen.queryByRole('link', { name: 'Cuéntanos qué pasó' })).toBeNull()
    window.location.hash = ''
  })
})

const PANEL = {
  items: [
    { id: 'p1', email: 'ana@test.com', tipo: 'problema', mensaje: 'No carga el extracto', pantalla: '/correos', version_app: '1.0',
      dispositivo: 'móvil · Chrome', puede_contactar: true, estado: 'nuevo', nota_admin: null, respuesta_publica: null,
      creado_en: '2026-10-01T10:00:00', actualizado_en: '2026-10-01T10:00:00' },
    { id: 'p2', email: 'luis@test.com', tipo: 'elogio', mensaje: 'Me encanta', pantalla: '/', version_app: null,
      dispositivo: 'escritorio · Edge', puede_contactar: false, estado: 'visto', nota_admin: 'gracias', respuesta_publica: null,
      creado_en: '2026-10-02T10:00:00', actualizado_en: '2026-10-02T10:00:00' },
  ],
  total: 2, pagina: 1, por_pagina: 30,
  por_estado: { nuevo: 1, visto: 1, en_curso: 0, resuelto: 0, descartado: 0 },
  por_tipo: { sugerencia: 0, problema: 1, pregunta: 0, elogio: 1 },
}

describe('Panel del administrador', () => {
  it('404 del servidor: no muestra datos', async () => {
    api.comentariosAdmin.mockRejectedValue(Object.assign(new Error('x'), { status: 404 }))
    montar(<ComentariosAdmin />, '/comentarios-admin')
    expect(await screen.findByText('Esta pantalla no está disponible')).toBeInTheDocument()
  })

  it('muestra resumen por estado y tipo y la lista; abre un comentario y guarda estado, nota y respuesta', async () => {
    api.comentariosAdmin.mockResolvedValue(PANEL)
    api.cambiarComentario.mockResolvedValue({ ...PANEL.items[0], estado: 'resuelto', nota_admin: 'revisado', respuesta_publica: 'Listo' })
    montar(<ComentariosAdmin />, '/comentarios-admin')
    expect(await screen.findByTestId('conteo-nuevo')).toHaveTextContent('1')
    fireEvent.click(screen.getByText('No carga el extracto'))
    expect(screen.getByText(/ana@test.com/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'resuelto' } })
    fireEvent.change(screen.getByLabelText('Nota interna'), { target: { value: 'revisado' } })
    fireEvent.change(screen.getByLabelText('Respuesta para la persona'), { target: { value: 'Listo' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
    await waitFor(() =>
      expect(api.cambiarComentario).toHaveBeenCalledWith('p1', { estado: 'resuelto', nota_admin: 'revisado', respuesta_publica: 'Listo' })
    )
  })

  it('filtra por estado y tipo y busca (pidiendo al servidor)', async () => {
    api.comentariosAdmin.mockResolvedValue(PANEL)
    montar(<ComentariosAdmin />, '/comentarios-admin')
    await screen.findByTestId('conteo-nuevo')
    fireEvent.click(within(screen.getByRole('group', { name: 'Filtrar por estado' })).getByRole('button', { name: 'Nuevo' }))
    await waitFor(() => expect(api.comentariosAdmin).toHaveBeenLastCalledWith(expect.objectContaining({ estado: 'nuevo' })))
    fireEvent.click(within(screen.getByRole('group', { name: 'Filtrar por tipo' })).getByRole('button', { name: /Algo falló/ }))
    await waitFor(() => expect(api.comentariosAdmin).toHaveBeenLastCalledWith(expect.objectContaining({ tipo: 'problema' })))
    fireEvent.change(screen.getByLabelText('Buscar'), { target: { value: 'extracto' } })
    await waitFor(() => expect(api.comentariosAdmin).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'extracto' })))
  })

  it('marca varios como vistos y exporta CSV', async () => {
    api.comentariosAdmin.mockResolvedValue(PANEL)
    api.marcarComentariosVistos.mockResolvedValue({ ok: true, actualizados: 1 })
    api.exportarComentariosCSV.mockResolvedValue()
    montar(<ComentariosAdmin />, '/comentarios-admin')
    await screen.findByTestId('conteo-nuevo')
    expect(screen.getByRole('button', { name: 'Marcar como vistos' })).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Marcar 1 como vistos' }))
    await waitFor(() => expect(api.marcarComentariosVistos).toHaveBeenCalledWith(['p1']))
    fireEvent.click(screen.getByRole('button', { name: 'Exportar CSV' }))
    await waitFor(() => expect(api.exportarComentariosCSV).toHaveBeenCalled())
  })
})
