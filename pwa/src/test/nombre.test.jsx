// «¿Cómo te llamamos?»: nombre de pila desde Google, validación, pantalla de captura y frases sin nombre.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({ usuario: { id: 'u1', email: 'dani@gmail.com', nombre: 'DANIEL ALFONSO PARRADO CARDENAS' } }),
}))

import PedirNombre from '../screens/PedirNombre'
import { conNombre, FRASES, frase } from '../lib/cuadri'
import { errorNombre, limpiarNombre, nombreDePila, reiniciarNombre } from '../lib/nombre'

describe('nombreDePila', () => {
  it.each([
    ['DANIEL ALFONSO PARRADO CARDENAS', '', 'Daniel'],
    ['daniel alfonso', '', 'Daniel'],
    ['María José Pérez', '', 'María'],
    ['María José Pérez', 'María José', 'María José'],
    ['MARÍA JOSÉ PÉREZ', 'MARÍA JOSÉ', 'María José'],
    ["O'BRIEN Kevin", '', "O'Brien"],
    ['McDonald Pérez', '', 'McDonald'],
    ['', '', ''],
    [undefined, undefined, ''],
    ['dani@gmail.com', '', ''],
    ['12345', '', ''],
    ['😀 Pepe', '', 'Pepe'],
  ])('%s + %s -> %s', (completo, pila, esperado) => {
    expect(nombreDePila(completo, pila)).toBe(esperado)
  })
})

describe('validación', () => {
  it.each(['Daniel', '  ana   maría ', 'José-Luis', "D'Angelo", 'Ñoño', 'a'.repeat(40)])('acepta %s', (t) => {
    expect(errorNombre(t)).toBe('')
    expect(limpiarNombre(t)).toBeTruthy()
  })
  it.each(['', '   ', '<b>Dani</b>', 'https://malo.co', 'www.malo.co', 'Dani 3001234567', 'Dani2', 'Dani 😀', '😀', 'a@b.co', 'a'.repeat(41), '---'])(
    'rechaza %s con mensaje amable',
    (t) => {
      expect(errorNombre(t)).toMatch(/\S/)
      expect(limpiarNombre(t)).toBe('')
    }
  )
  it('recorta y deja el formato Nombre', () => {
    expect(limpiarNombre('  ana   maría ')).toBe('Ana María')
    expect(limpiarNombre('ÁNGELA')).toBe('Ángela')
  })
})

describe('frases con nombre', () => {
  it('pone el nombre y, sin nombre, la frase se lee bien', () => {
    expect(conNombre('¡Hola, {nombre}! Soy Cuadri.', 'Daniel')).toBe('¡Hola, Daniel! Soy Cuadri.')
    expect(conNombre('¡Hola, {nombre}! Soy Cuadri.', '')).toBe('¡Hola! Soy Cuadri.')
    expect(conNombre('¡Meta cumplida, {nombre}! Eso sí cuadra.', '  ')).toBe('¡Meta cumplida! Eso sí cuadra.')
    expect(conNombre('Sin marcador', 'Daniel')).toBe('Sin marcador')
  })
  it('ninguna frase deja llaves, "Hola, !" ni comas sueltas sin nombre', () => {
    const todas = [...Object.values(FRASES).flatMap((v) => (Array.isArray(v) ? v : Object.values(v)))]
    for (const t of todas) {
      const sin = conNombre(t, '')
      expect(sin).not.toMatch(/[{}]|,\s*[!.?]|\s{2,}/)
      expect(conNombre(t, 'Daniel')).not.toMatch(/[{}]/)
    }
    expect(frase('saludo', 0)).not.toMatch(/\{/)
    expect(frase('saludo', 0, 'Daniel')).toContain('Daniel')
  })
})

describe('PedirNombre', () => {
  beforeEach(() => {
    reiniciarNombre()
    api.nombrePerfil = vi.fn().mockResolvedValue({ nombre: null, sugerido: 'Daniel', confirmado: false, email: 'dani@gmail.com' })
    api.guardarNombrePerfil = vi.fn().mockImplementation((d) =>
      Promise.resolve({ nombre: d.nombre || 'Daniel', sugerido: 'Daniel', confirmado: true, email: 'dani@gmail.com' })
    )
  })

  async function montar(onListo = vi.fn()) {
    render(<PedirNombre onListo={onListo} />)
    return { onListo, campo: await screen.findByLabelText('Cómo te llamamos') }
  }

  it('prellena con el nombre de pila, tiene foco inicial y ayuda', async () => {
    const { campo } = await montar()
    await waitFor(() => expect(campo).toHaveValue('Daniel'))
    expect(campo).toHaveFocus()
    expect(screen.getByRole('heading', { name: '¿Cómo te llamamos?' })).toBeInTheDocument()
    expect(screen.getByText('Así te saludamos en la app, los avisos y los correos.')).toBeInTheDocument()
    expect(screen.getAllByRole('textbox')).toHaveLength(1) // pide SOLO el nombre
  })

  it('«Listo» guarda el nombre editado y Enter también envía', async () => {
    const { campo, onListo } = await montar()
    await userEvent.clear(campo)
    await userEvent.type(campo, 'dani{Enter}')
    await waitFor(() => expect(onListo).toHaveBeenCalled())
    expect(api.guardarNombrePerfil).toHaveBeenCalledWith({ nombre: 'Dani' })
  })

  it('con un nombre inválido avisa con amabilidad y no guarda', async () => {
    const { campo, onListo } = await montar()
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Dani 😀')
    await userEvent.click(screen.getByRole('button', { name: 'Listo' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/solo letras/i)
    expect(api.guardarNombrePerfil).not.toHaveBeenCalled()
    expect(onListo).not.toHaveBeenCalled()
  })

  it('«Ahora no» usa el nombre automático y deja pasar', async () => {
    const { onListo } = await montar()
    await userEvent.click(screen.getByRole('button', { name: 'Ahora no' }))
    await waitFor(() => expect(onListo).toHaveBeenCalled())
    expect(api.guardarNombrePerfil).toHaveBeenCalledWith({ omitir: true })
  })

  it('«Ahora no» sin conexión igual deja pasar', async () => {
    api.guardarNombrePerfil = vi.fn().mockRejectedValue(new Error('sin red'))
    const { onListo } = await montar()
    await userEvent.click(screen.getByRole('button', { name: 'Ahora no' }))
    await waitFor(() => expect(onListo).toHaveBeenCalled())
  })

  it('persona sin nombre en Google: campo vacío y se puede escribir', async () => {
    api.nombrePerfil = vi.fn().mockResolvedValue({ nombre: null, sugerido: null, confirmado: false })
    const { campo } = await montar()
    expect(campo).toHaveValue('')
    await userEvent.click(screen.getByRole('button', { name: 'Listo' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/Escribe cómo/)
  })
})
