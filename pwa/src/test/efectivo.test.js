import { describe, it, expect, beforeEach } from 'vitest'
import {
  sugerenciaEfectivo,
  cuentaEfectivoPara,
  ofertaEfectivo,
  cuentaInicial,
  guardarUltimaCuenta,
  leerUltimaCuenta,
} from '../lib/efectivo'

describe('sugerenciaEfectivo (espejo del backend)', () => {
  it('retiro de cajero y corresponsal es traslado, no gasto', () => {
    expect(sugerenciaEfectivo('expense', 'Retiro cajero Bancolombia')).toBe('retiro')
    expect(sugerenciaEfectivo('expense', 'RETIRO CORRESPONSAL')).toBe('retiro')
  })
  it('consignación en efectivo es el inverso', () => {
    expect(sugerenciaEfectivo('income', 'Consignación en efectivo')).toBe('deposito')
  })
  it('un cobro por retiro sigue siendo gasto; compras normales no aplican', () => {
    expect(sugerenciaEfectivo('expense', 'Comisión retiro cajero ajeno')).toBeNull()
    expect(sugerenciaEfectivo('expense', 'Compra Éxito')).toBeNull()
    expect(sugerenciaEfectivo('income', 'Retiro cajero')).toBeNull()
  })
})

describe('cuenta de efectivo y última cuenta', () => {
  const cuentas = [
    { id: 'a', tipo: 'ahorro', moneda: 'COP' },
    { id: 'e', tipo: 'efectivo', moneda: 'COP' },
    { id: 'eu', tipo: 'efectivo', moneda: 'USD' },
  ]
  beforeEach(() => localStorage.clear())

  it('elige el efectivo de la misma moneda', () => {
    expect(cuentaEfectivoPara(cuentas, { moneda: 'USD' }).id).toBe('eu')
    expect(cuentaEfectivoPara([cuentas[0]], { moneda: 'COP' })).toBeNull()
  })
  it('el texto cambia si no hay cuenta de efectivo', () => {
    expect(ofertaEfectivo('retiro', true).boton).toBe('Sí, pasarlo')
    expect(ofertaEfectivo('retiro', false).boton).toBe('Crear mi efectivo y pasarlo')
  })
  it('recuerda la última cuenta y cae a la primera si ya no existe', () => {
    expect(cuentaInicial(cuentas, leerUltimaCuenta('u1'))).toBe('a')
    guardarUltimaCuenta('u1', 'e')
    expect(cuentaInicial(cuentas, leerUltimaCuenta('u1'))).toBe('e')
    expect(cuentaInicial(cuentas, 'borrada')).toBe('a')
    expect(cuentaInicial([], '')).toBe('')
  })
})
