import { describe, it, expect } from 'vitest'
import { textoError } from '../lib/textoError'
import { traducirError } from '../lib/AuthContext'
import { formatCOP, formatMoneda } from '../lib/format'

describe('textoError', () => {
  it('sin internet', () => {
    expect(textoError({ sinConexion: true, message: 'x' }, 'guardar')).toMatch(/no tienes internet/)
    expect(textoError(new TypeError('Failed to fetch'), 'guardar')).toMatch(/no tienes internet/)
  })
  it('usa el mensaje de la API si lo hay', () => {
    expect(textoError(new Error('El monto debe ser mayor a cero'), 'guardar')).toBe('El monto debe ser mayor a cero')
  })
  it('si no hay mensaje, dice qué no se pudo hacer', () => {
    expect(textoError(new Error(''), 'guardar la meta')).toBe('No pudimos guardar la meta. Intenta de nuevo en un momento.')
    expect(textoError(undefined, 'guardar')).toBe('No pudimos guardar. Intenta de nuevo en un momento.')
  })
})

describe('traducirError', () => {
  it('cada caso tiene su mensaje y no revienta con undefined', () => {
    expect(traducirError(undefined)).toBe('')
    expect(traducirError('Email address "x" is invalid')).toMatch(/correo no parece válido/)
    expect(traducirError('Token has expired or is invalid')).toMatch(/código no es correcto/)
    expect(traducirError('Invalid login credentials')).toMatch(/contraseña incorrectos/)
    expect(traducirError('invalid something')).toMatch(/no es válido/)
  })
})

describe('formatCOP / formatMoneda sin valor', () => {
  it('devuelve «—» y no «$ NaN»', () => {
    expect(formatCOP(undefined)).toBe('—')
    expect(formatCOP(NaN)).toBe('—')
    expect(formatMoneda(undefined, 'USD')).toBe('—')
    expect(formatCOP(0)).toMatch(/0/)
  })
})
