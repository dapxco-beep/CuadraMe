// Tras autorizar la IA, la pregunta pendiente se reenvía sola y los chips de sugerencias siguen.
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import Asistente from '../screens/Asistente'
import ConsentimientoGlobal from '../components/ConsentimientoGlobal'

const PREGUNTA = '¿En qué gasté más este mes?'

function consentimientoRequerido() {
  const err = new Error('Falta una autorización')
  err.codigo = 'consentimiento_requerido'
  err.finalidad = 'ia'
  // lo que hace api.js al recibir el 403
  window.dispatchEvent(new CustomEvent('cuadrame:consentimiento', { detail: { finalidad: 'ia' } }))
  return Promise.reject(err)
}

function montar() {
  return render(
    <MemoryRouter>
      <Asistente />
      <ConsentimientoGlobal />
    </MemoryRouter>
  )
}

beforeEach(() => {
  api.asistenteSugerencias = vi.fn().mockResolvedValue({ preguntas: [{ id: 'g', texto: PREGUNTA }], oportunidades: [] })
  api.guardarConsentimientos = vi.fn().mockResolvedValue({})
  api.asistenteMensaje = vi.fn().mockImplementationOnce(consentimientoRequerido).mockResolvedValue({
    tipo: 'respuesta', texto: 'En octubre llevas $80.000.', fuentes: [],
  })
})

describe('Asistente + consentimiento de IA', () => {
  it('al autorizar reenvía la pregunta pendiente y no pide "vuelve a intentarlo"', async () => {
    montar()
    await userEvent.click(await screen.findByRole('button', { name: PREGUNTA }))
    // mientras se decide: la pregunta no queda como mensaje y los chips siguen
    expect(await screen.findByText(/necesito tu autorización de IA/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: PREGUNTA })).toBeInTheDocument()

    await userEvent.click(await screen.findByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Autorizo' }))

    expect(await screen.findByText('En octubre llevas $80.000.')).toBeInTheDocument()
    expect(api.asistenteMensaje).toHaveBeenCalledTimes(2)
    expect(api.asistenteMensaje).toHaveBeenLastCalledWith(PREGUNTA)
    expect(screen.queryByText(/Vuelve a intentarlo/)).toBeNull()
  })

  it('si dice "Ahora no", la pregunta vuelve al cuadro de texto y siguen los chips', async () => {
    montar()
    await userEvent.click(await screen.findByRole('button', { name: PREGUNTA }))
    await userEvent.click(await screen.findByRole('button', { name: 'Ahora no' }))
    await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue(PREGUNTA))
    expect(screen.getByRole('button', { name: PREGUNTA })).toBeInTheDocument()
    expect(api.asistenteMensaje).toHaveBeenCalledTimes(1)
  })
})
