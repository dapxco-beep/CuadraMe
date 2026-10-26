import { beforeEach, describe, expect, it } from 'vitest'
import { avisoVisible, claveCuadre, guardarOcultos, leerOcultos } from '../lib/avisoCuadre'

const nu = { cuenta_id: 'c1', cuenta: 'Nu Colombia Crédito', estado: 'no_cuadra', mes: '2026-10', diferencia: -160000, texto: 'No cuadra en octubre (dif. $160.000)' }
const nequi = { cuenta_id: 'c2', cuenta: 'Nequi', estado: 'cuadra', mes: '2026-09', diferencia: 0, texto: 'Cuadra a septiembre' }

describe('aviso de cuadre ocultable', () => {
  beforeEach(() => localStorage.clear())

  it('sin cuentas que no cuadren no hay aviso', () => {
    expect(avisoVisible({ cuentas: [nequi] })).toBeNull()
    expect(avisoVisible(null)).toBeNull()
  })

  it('muestra la cuenta que no cuadra, con su diferencia', () => {
    const a = avisoVisible({ cuentas: [nequi, nu] })
    expect(a.n).toBe(1)
    expect(a.texto).toBe('Nu Colombia Crédito: no cuadra en octubre (dif. $160.000)')
  })

  it('al ocultarlo no vuelve mientras la diferencia sea la misma, y se guarda en el dispositivo', () => {
    const a = avisoVisible({ cuentas: [nu] })
    guardarOcultos(a.claves)
    expect(leerOcultos()).toEqual([claveCuadre(nu)])
    expect(avisoVisible({ cuentas: [nu] }, leerOcultos())).toBeNull()
  })

  it('si la diferencia cambia, el aviso vuelve a salir', () => {
    guardarOcultos([claveCuadre(nu)])
    const cambiada = { ...nu, diferencia: -314542 }
    expect(avisoVisible({ cuentas: [cambiada] }, leerOcultos())).not.toBeNull()
  })

  it('ocultar una cuenta no oculta a otra que también no cuadra', () => {
    const otra = { ...nu, cuenta_id: 'c3', cuenta: 'Bancolombia' }
    const a = avisoVisible({ cuentas: [nu, otra] }, [claveCuadre(nu)])
    expect(a.n).toBe(1)
    expect(a.texto.startsWith('Bancolombia')).toBe(true)
  })

  it('el signo de la diferencia no cambia la clave (-160000 y 160000 son lo mismo)', () => {
    expect(claveCuadre({ ...nu, diferencia: 160000 })).toBe(claveCuadre(nu))
  })
})
