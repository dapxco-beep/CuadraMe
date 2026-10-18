// «Estado por cuenta y mes»: una tarjeta por cuenta con una fila de meses, cada mes con UN estado que se entiende
// solo y una acción lógica al tocarlo. Puro (sin React) y probado en test/estado_por_cuenta.test.js.
// Reutiliza lo que ya calcula GET /sincronizacion/estado (cuentas → meses): nada se recalcula aquí.

export const TIPO_CUENTA_TEXTO = { ahorro: 'Ahorros', credito: 'Tarjeta', efectivo: 'Efectivo', inversion: 'Inversión' }

/** «Nu Colombia · Ahorros», «Nu Colombia Crédito · Tarjeta»: el nombre COMPLETO y qué tipo de cuenta es. */
export const tipoDeCuenta = (c) => TIPO_CUENTA_TEXTO[c?.tipo] || 'Ahorros'
export const nombreCompleto = (c) => `${c?.nombre || 'Cuenta'} · ${tipoDeCuenta(c)}`

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`
const pidePorClave = (motivo) => /clave/i.test(motivo || '')

/**
 * Cómo se ve y qué hace un mes de una cuenta.
 *  clave:  conciliado | falta_importar | no_se_pudo_leer | falta_extracto | en_curso | otra_cuenta | anterior
 *  accion: ver | importar | clave | revisar_error | subir | pasar | ninguna
 * `esMesActual`: el mes que aún no termina no tiene extracto todavía; no es «falta» sino «en curso».
 */
export function vistaCelda(celda, { esMesActual = false } = {}) {
  const c = celda || {}
  const otra = (c.en_otra_cuenta || [])[0]
  switch (c.estado) {
    case 'anterior':
      return { clave: 'anterior', texto: 'Antes de tu inicio', detalle: '', accion: 'ninguna' }
    case 'conciliado':
      return { clave: 'conciliado', texto: 'Conciliado', detalle: c.movimientos ? `${plural(c.movimientos, 'mov.', 'mov.')}` : '', accion: 'ver' }
    case 'parcial':
      return {
        clave: 'falta_importar',
        texto: c.por_revisar ? `Falta importar ${c.por_revisar}` : 'Falta importar',
        detalle: c.lectura_dudosa ? 'Elige un monto' : 'Revisa y agrega',
        accion: 'importar',
      }
    case 'extracto_pendiente':
      return { clave: 'falta_importar', texto: 'Falta importar', detalle: 'Llegó, sin revisar', accion: 'importar' }
    case 'falta_clave':
      return { clave: 'no_se_pudo_leer', texto: 'No se pudo leer', detalle: c.motivo_corto || 'falta la clave', accion: 'clave' }
    case 'no_se_pudo_leer':
      return {
        clave: 'no_se_pudo_leer',
        texto: 'No se pudo leer',
        detalle: c.motivo_corto || 'no se leyó el PDF',
        accion: pidePorClave(c.motivo_corto) ? 'clave' : 'revisar_error',
      }
    default: {
      // sin_extracto (hay movimientos pero ningún extracto) o vacio
      if (otra) return { clave: 'otra_cuenta', texto: 'En otra cuenta', detalle: `Está en ${otra.desde}`, accion: 'pasar' }
      if (esMesActual) return { clave: 'en_curso', texto: 'Mes en curso', detalle: 'El extracto llega al cerrar', accion: 'subir' }
      return {
        clave: 'falta_extracto',
        texto: 'Falta el extracto',
        detalle: c.movimientos ? `${plural(c.movimientos, 'mov.', 'mov.')} sin extracto` : '',
        accion: 'subir',
      }
    }
  }
}

/** «3 de 6 meses completos». No cuenta lo anterior a tu fecha de inicio ni el mes que aún no termina. */
export function resumenMeses(vistas) {
  const cuentan = (vistas || []).filter((v) => v.clave !== 'anterior' && v.clave !== 'en_curso')
  if (cuentan.length === 0) return 'Aún sin meses por revisar'
  const completos = cuentan.filter((v) => v.clave === 'conciliado').length
  return `${completos} de ${cuentan.length} ${cuentan.length === 1 ? 'mes completo' : 'meses completos'}`
}

/** Las cuentas que tienen extracto (el efectivo no). */
export const cuentasConExtracto = (cuentas) => (cuentas || []).filter((c) => c.tipo !== 'efectivo')

/** 'AAAA-MM' de hoy. */
export const mesDeHoy = (hoy = new Date()) => `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`
