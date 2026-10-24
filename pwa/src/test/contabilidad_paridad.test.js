// Paridad Python <-> JS: los MISMOS casos (backend/tests/fixtures/contabilidad_casos.json) que prueba
// backend/tests/test_traslados_robustos.py. Si cambia la regla en un lado, esta prueba obliga a cambiar el otro.
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  aBase,
  clasificar,
  contextoDeCuentas,
  huellaTraslado,
  mencionesPropias,
  tipoEfectivo,
  tiposEfectivos,
  totalesIngresosGastos,
} from '../lib/contabilidad'

const { casos } = JSON.parse(readFileSync(resolve(__dirname, '../../../backend/tests/fixtures/contabilidad_casos.json'), 'utf-8'))

function ctxDe(caso) {
  const cuentas = Object.entries(caso.cuentas).map(([id, v]) => ({ id, tipo: v.tipo, moneda: v.moneda }))
  return contextoDeCuentas(cuentas, { reglas: caso.reglas, nombres: caso.nombres })
}

describe('paridad de moneda base (backend/tests/fixtures/moneda_base_casos.json)', () => {
  const { casos: casosBase } = JSON.parse(
    readFileSync(resolve(__dirname, '../../../backend/tests/fixtures/moneda_base_casos.json'), 'utf-8'),
  )
  for (const caso of casosBase) {
    it(caso.nombre, () => {
      const [v, ok] = aBase(caso.monto, caso.origen, caso.base, caso.tasas)
      expect([Number(v.toFixed(6)), ok]).toEqual(caso.esperado)
    })
  }
})

describe('paridad con backend/app/contabilidad.py', () => {
  for (const caso of casos) {
    it(caso.nombre, () => {
      expect(tiposEfectivos(caso.movs, ctxDe(caso))).toEqual(caso.esperado)
    })
  }

  it('razón y pareja del par', () => {
    const cl = clasificar(casos[0].movs, ctxDe(casos[0]))
    expect(cl.e).toEqual({ tipo: 'transfer', razon: 'par', par: 'i' })
  })

  it('huella y nombre parcial igual que el servidor', () => {
    expect(huellaTraslado('Enviaste a Ana Lopez 123456')).toBe('ana lopez')
    expect(huellaTraslado('Recibiste de ANA  LÓPEZ')).toBe('ana lopez')
    expect(huellaTraslado('Para 1234')).toBe('')
    expect(mencionesPropias('ENVIASTE A DANIEL PARRADO', ['Daniel Alfonso Parrado Cárdenas'])).toBe(2)
    expect(mencionesPropias('Enviaste a Daniel Gomez', ['Daniel Alfonso Parrado Cárdenas'])).toBe(1)
  })

  it('tipoEfectivo individual no empareja', () => {
    expect(tipoEfectivo({ tipo: 'expense', descripcion: 'Pago tarjeta de credito', categoria: 'Otros' })).toBe('transfer')
    expect(tipoEfectivo({ tipo: 'expense', descripcion: 'Enviaste a Ana', categoria: 'Transferencias' })).toBe('expense')
  })

  it('totales con traslados presentes no cambian ingresos ni gastos', () => {
    const base = [
      { id: 'i', tipo: 'income', monto: 1000, descripcion: 'Nomina', cuenta_id: 'N', categoria: 'Otros', fecha: '2026-10-05T12:00:00' },
      { id: 'g', tipo: 'expense', monto: 300, descripcion: 'Mercado', cuenta_id: 'N', categoria: 'Otros', fecha: '2026-10-05T12:00:00' },
    ]
    const tras = [
      { id: 'e', tipo: 'expense', monto: 500, descripcion: 'Enviaste a Ana', cuenta_id: 'N', categoria: 'Otros', fecha: '2026-10-05T12:00:00' },
      { id: 'r', tipo: 'income', monto: 500, descripcion: 'Recibiste de Ana', cuenta_id: 'U', categoria: 'Otros', fecha: '2026-10-05T12:00:00' },
    ]
    const ctx = { tipos: { N: 'ahorro', U: 'ahorro' } }
    const sin = totalesIngresosGastos(base, ctx)
    const con = totalesIngresosGastos([...base, ...tras], ctx)
    expect(con).toEqual(sin)
    expect(con.balance).toBe(700)
    expect(con.tasaAhorro).toBe(70)
  })
})

describe('totalesConTipos (subtotales de Movimientos)', () => {
  it('el traslado entre mis cuentas no suma ni resta; el gasto a un tercero sí', async () => {
    const { totalesConTipos, tiposEfectivos } = await import('../lib/contabilidad')
    const movs = [
      { id: 1, tipo: 'income', monto: 1000, cuenta_id: 'a', fecha: '2026-10-01', descripcion: 'Sueldo' },
      { id: 2, tipo: 'expense', monto: 300, cuenta_id: 'a', fecha: '2026-10-01', descripcion: 'Mercado' },
      { id: 3, tipo: 'transfer', monto: 500, cuenta_id: 'a', fecha: '2026-10-01', descripcion: 'TRF', notas: 'TRF:x:out' },
      { id: 4, tipo: 'transfer', monto: 500, cuenta_id: 'b', fecha: '2026-10-01', descripcion: 'TRF', notas: 'TRF:x:in' },
    ]
    const te = tiposEfectivos(movs, {})
    const t = totalesConTipos(movs, te)
    expect(t.ingresos).toBe(1000)
    expect(t.gastos).toBe(300)
    expect(t.neto).toBe(700)
  })
})

describe('ingreso en tarjeta de crédito', () => {
  it('es abono (neutral) salvo que la persona lo marque como ingreso real', async () => {
    const { tiposEfectivos } = await import('../lib/contabilidad')
    const base = { tipo: 'income', cuenta_id: 'T', fecha: '2026-10-20', fuente: 'manual', categoria: 'Ingresos' }
    const te = tiposEfectivos(
      [{ ...base, id: 1, monto: 80000, descripcion: 'Sk' }, { ...base, id: 2, monto: 90000, descripcion: 'Sk', notas: 'no_es_traslado' }],
      { tipos: { T: 'credito' } }
    )
    expect(te[1]).toBe('transfer')
    expect(te[2]).toBe('income')
  })
})
