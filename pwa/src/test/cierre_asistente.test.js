import { describe, expect, it } from 'vitest'
import { cosasRaras, cuentasDelCierre, estadoPasos, listoParaCerrar, pendientesDeCierre, textoAvance } from '../lib/cierreAsistente'

const ext = (...estados) => ({ hay_datos: true, bancos: [{ banco: 'Nu', cuentas: estados.map((estado, i) => ({ cuenta_id: `c${i}`, estado })) }] })
const ids = (pasos) => pasos.map((p) => `${p.id}:${p.estado}`)

describe('pasos del cierre de mes', () => {
  it('mientras carga, los pasos están en «cargando» y no se puede cerrar', () => {
    const pasos = estadoPasos({})
    expect(ids(pasos)).toEqual(['cuentas:cargando', 'categorias:cargando', 'raro:cargando', 'resumen:neutro'])
    expect(listoParaCerrar(pasos)).toBe(false)
  })

  it('todo en orden: listo para cerrar', () => {
    const pasos = estadoPasos({ ext: ext('cuadra', 'cuadra'), porCategorizar: 0, alertas: { comisiones: [], cobros_duplicados: [] } })
    expect(ids(pasos)).toEqual(['cuentas:ok', 'categorias:ok', 'raro:ok', 'resumen:neutro'])
    expect(listoParaCerrar(pasos)).toBe(true)
    expect(pasos[0].resumen).toBe('Todas tus cuentas cuadran con el banco.')
  })

  it('cuentas que no cuadran o sin extracto piden atención, con la cantidad en palabras', () => {
    expect(estadoPasos({ ext: ext('cuadra', 'no_cuadra') })[0]).toMatchObject({ estado: 'atencion', cantidad: 1, resumen: '1 cuenta no cuadra con tu banco.' })
    expect(estadoPasos({ ext: ext('no_cuadra', 'no_cuadra') })[0].resumen).toBe('2 cuentas no cuadran con tu banco.')
    expect(estadoPasos({ ext: ext('cuadra', 'sin_extracto') })[0].resumen).toBe('Falta el extracto de 1 cuenta.')
  })

  it('un mes sin datos o sin poder comparar no bloquea (es neutro)', () => {
    expect(estadoPasos({ ext: { hay_datos: false, bancos: [] } })[0].estado).toBe('neutro')
    expect(estadoPasos({ ext: false })[0].estado).toBe('neutro')
  })

  it('categorías sin poner y cosas raras piden atención', () => {
    const pasos = estadoPasos({
      ext: ext('cuadra'), porCategorizar: 12,
      alertas: { comisiones: [{ descripcion: 'Cuota de manejo', total_mes: 20000, veces: 1 }], cobros_duplicados: [{ movimiento_id_1: 'm1', descripcion: 'Netflix', monto: 30000 }] },
    })
    expect(pasos[1]).toMatchObject({ estado: 'atencion', resumen: '12 comercios sin categoría.' })
    expect(pasos[2]).toMatchObject({ estado: 'atencion', cantidad: 2, resumen: '2 cosas para mirar.' })
    expect(pendientesDeCierre(pasos).map((p) => p.id)).toEqual(['categorias', 'raro'])
    expect(listoParaCerrar(pasos)).toBe(false)
    expect(textoAvance(1, pasos)).toBe('Paso 2 de 4 · 2 por resolver')
  })

  it('un solo comercio sin categoría usa el singular', () => {
    expect(estadoPasos({ porCategorizar: 1 })[1].resumen).toBe('1 comercio sin categoría.')
  })

  it('el último paso refleja si ya existe el cierre', () => {
    expect(estadoPasos({ informe: { ahorro: 1 } })[3].estado).toBe('ok')
    expect(estadoPasos({ informe: false })[3].estado).toBe('neutro')
  })

  it('no explota con datos incompletos', () => {
    expect(cuentasDelCierre(null)).toEqual([])
    expect(cosasRaras(null)).toEqual([])
    expect(textoAvance(0, [])).toBe('Paso 1 de 4')
  })
})
