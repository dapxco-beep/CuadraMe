// Varias cuentas del MISMO banco (ej. «Nu Colombia» de ahorros y «Nu Tarjeta» de crédito).
// El nombre del banco no dice a cuál va un movimiento: se muestra el TIPO en lenguaje simple
// y se recuerda la elección de la persona para ese banco + tipo.

const sinTildes = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

// Palabras que describen el producto y no al banco (no sirven para saber si son del mismo banco).
const GENERICAS = new Set([
  'tarjeta', 'credito', 'debito', 'ahorro', 'ahorros', 'cuenta', 'visa', 'mastercard', 'master',
  'amex', 'banco', 'colombia', 'tdc', 'tc', 'de', 'del', 'la', 'el', 'mi', 'mis', 'para', 'con', 'wallet',
])

/** Palabras que identifican la entidad: 'Nu Tarjeta' -> ['nu']. */
export function marcaDe(nombre) {
  return sinTildes(nombre).split(/[^a-z0-9]+/).filter((w) => w.length >= 2 && !/^\d+$/.test(w) && !GENERICAS.has(w))
}

export const esCredito = (c) => (c?.tipo || '') === 'credito'

/** 'Tarjeta de crédito' | 'Débito/Ahorros' | '' (efectivo, inversión...). */
export function etiquetaTipo(c) {
  if (esCredito(c)) return 'Tarjeta de crédito'
  if (['ahorro', 'corriente', 'debito', 'nomina', '', undefined, null].includes(c?.tipo)) return 'Débito/Ahorros'
  return ''
}

/** 'credito' | 'debito' | null según palabras del texto (nombre de archivo, asunto...). */
export function productoDeTexto(texto) {
  const t = sinTildes(texto)
  const c = /tarjeta|credito|\bcupo\b|pago minimo|\btdc\b/.test(t)
  const d = /ahorro|debito|cuenta corriente|cajita|saldo disponible/.test(t)
  if (c === d) return null
  return c ? 'credito' : 'debito'
}

/** Cuentas que comparten banco con `cuenta` (incluida ella). */
export function mismasDelBanco(cuenta, cuentas) {
  const m = marcaDe(cuenta?.nombre)
  if (!m.length) return [cuenta]
  return cuentas.filter((c) => c.id === cuenta.id || marcaDe(c.nombre).some((w) => m.includes(w)))
}

/** Texto de la opción: solo agrega el tipo cuando el banco tiene más de una cuenta. */
export function textoOpcionCuenta(cuenta, cuentas) {
  const et = etiquetaTipo(cuenta)
  if (!et || mismasDelBanco(cuenta, cuentas).length < 2) return cuenta.nombre
  return `${cuenta.nombre} · ${et}`
}

// ── Memoria de la elección (por banco + tipo) ─────────────────────
const clave = (banco, producto) => `cuadrame.cuentaBanco.${marcaDe(banco).join('-') || sinTildes(banco)}.${producto || 'x'}`

export function recordarCuenta(banco, producto, cuentaId) {
  if (!banco || !cuentaId) return
  try {
    localStorage.setItem(clave(banco, producto), cuentaId)
  } catch { /* sin almacenamiento: no pasa nada */ }
}

/** Cuenta que la persona eligió antes para ese banco+tipo (solo si todavía existe). */
export function cuentaRecordada(banco, producto, cuentas) {
  if (!banco) return ''
  try {
    const id = localStorage.getItem(clave(banco, producto))
    return id && cuentas.some((c) => c.id === id) ? id : ''
  } catch {
    return ''
  }
}
