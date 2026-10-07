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

export const TIPO_LABEL = { ahorro: 'Ahorros', efectivo: 'Efectivo', credito: 'Tarjetas de crédito', inversion: 'Inversión' }

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
