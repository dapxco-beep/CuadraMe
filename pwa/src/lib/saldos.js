// Ayudas puras para que el "saldo actual" sea inequívoco en Inicio y Cuentas.

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

// Las fechas del backend vienen en hora Colombia SIN zona ("2026-10-03T14:05:00").
// Se parten a mano: new Date() las leería según la zona del teléfono y podría correr un día.
function partes(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? { a: +m[1], m: +m[2], d: +m[3] } : null
}

// "actualizado hoy" | "último movimiento: ayer" | "último movimiento: 3 oct" | "sin movimientos aún"
export function textoActualizado(iso, hoy = new Date()) {
  const p = partes(iso)
  if (!p) return 'sin movimientos aún'
  const h = Date.UTC(hoy.getFullYear(), hoy.getMonth(), hoy.getDate())
  const dias = Math.round((h - Date.UTC(p.a, p.m - 1, p.d)) / 86400000)
  if (dias <= 0) return 'actualizado hoy'
  if (dias === 1) return 'último movimiento: ayer'
  return `último movimiento: ${p.d} ${MESES[p.m - 1]}`
}

// Una tarjeta de crédito guarda saldo NEGATIVO cuando debes (-800.000 = debes 800.000).
export function esCredito(cuenta) {
  return cuenta?.tipo === 'credito'
}

export function deudaTarjeta(cuenta) {
  return Math.max(0, -(cuenta?.saldo || 0))
}

// Disponible del cupo: lo calcula el backend (cupo - usado); sin cupo configurado es null.
export function cupoDisponible(cuenta) {
  return cuenta?.tarjeta?.cupo_disponible ?? null
}

// Etiqueta clara de qué ES una cuenta y qué significa su saldo. La diferencia débito/crédito es lo que más
// confunde: en una cuenta de ahorros el número es plata TUYA; en una tarjeta de crédito es lo que DEBES.
//  - etiqueta: el nombre corto del tipo ("Débito / Ahorros" | "Tarjeta de crédito" | ...)
//  - significado: qué dice el número que se ve
//  - termino: id del glosario de «Aprende» para el botón «¿qué es esto?»
export function etiquetaCuenta(cuenta) {
  switch (cuenta?.tipo) {
    case 'credito':
      return {
        etiqueta: 'Tarjeta de crédito',
        significado: 'Lo que ves es lo que debes al banco, no plata tuya. Pagarla no es un gasto nuevo.',
        termino: 'credito',
      }
    case 'efectivo':
      return { etiqueta: 'Efectivo', significado: 'Plata tuya que tienes en la mano.', termino: 'saldo-disponible' }
    case 'inversion':
      return { etiqueta: 'Inversión', significado: 'Plata tuya invertida; su valor puede subir o bajar.', termino: 'saldo-disponible' }
    default:
      return {
        etiqueta: 'Débito / Ahorros',
        significado: 'Saldo disponible: plata tuya que puedes usar ya.',
        termino: 'saldo-disponible',
      }
  }
}

export const TIPO_LABEL ={ ahorro: 'Ahorros', efectivo: 'Efectivo', credito: 'Tarjetas de crédito', inversion: 'Inversión' }

// Modos del selector del héroe: total | moneda | tipo
export function filasPorModo(modo, resumen) {
  if (!resumen) return []
  if (modo === 'moneda') {
    return Object.entries(resumen.por_moneda || {}).map(([moneda, valor]) => ({ clave: moneda, etiqueta: moneda, valor, moneda }))
  }
  if (modo === 'tipo') {
    return Object.entries(resumen.por_tipo || {}).map(([tipo, valor]) => ({ clave: tipo, etiqueta: TIPO_LABEL[tipo] || tipo, valor, moneda: 'COP' }))
  }
  return []
}
