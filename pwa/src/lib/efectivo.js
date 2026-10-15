// Efectivo: reconocer retiros de cajero y depósitos, y recordar la última cuenta usada.
// Espejo de backend/app/efectivo.py (misma regla: un retiro NO es un gasto, es un traslado
// banco -> Efectivo; una consignación en efectivo es el traslado inverso).

const RETIRO = /\b(retiro|retiros|cajero|corresponsal|atm|avance en efectivo)\b/
const COBRO = /\b(comision|cobro|costo|cuota de manejo|iva)\b/
const DEPOSITO =
  /\b(deposito|consignacion|consig)\b.*\b(efectivo|cajero|corresponsal|ventanilla|sucursal)\b|\b(deposito|consignacion) en efectivo\b|\bconsignacion\b/

function norm(texto) {
  return String(texto || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
}

/** 'retiro' | 'deposito' | null. Solo con la dirección correcta (retiro = gasto, depósito = ingreso). */
export function sugerenciaEfectivo(tipo, descripcion) {
  const d = norm(descripcion)
  if (!d) return null
  if (tipo === 'expense' && RETIRO.test(d) && !COBRO.test(d)) return 'retiro'
  if (tipo === 'income' && DEPOSITO.test(d)) return 'deposito'
  return null
}

/** Cuenta Efectivo de la misma moneda que la cuenta del banco, o null. */
export function cuentaEfectivoPara(cuentas, cuentaBanco) {
  const moneda = cuentaBanco?.moneda || 'COP'
  return (cuentas || []).find((c) => c.tipo === 'efectivo' && (c.moneda || 'COP') === moneda) || null
}

/** Texto de la oferta, según haya o no cuenta de efectivo. */
export function ofertaEfectivo(sentido, tieneEfectivo) {
  const pregunta = sentido === 'retiro' ? '¿Lo pasamos a tu efectivo?' : '¿Lo sacamos de tu efectivo?'
  const apoyo =
    sentido === 'retiro'
      ? 'Sacar plata del cajero no es un gasto: es plata que pasa de tu banco a tu bolsillo.'
      : 'Consignar efectivo no es un ingreso nuevo: es plata que pasa de tu bolsillo al banco.'
  const boton = tieneEfectivo ? 'Sí, pasarlo' : 'Crear mi efectivo y pasarlo'
  return { pregunta, apoyo, boton }
}

// ── Última cuenta usada (por persona, solo en este celular) ─────────────────
const clave = (usuarioId) => `cuadrame.ultimaCuenta.${usuarioId || 'anon'}`

export function guardarUltimaCuenta(usuarioId, cuentaId) {
  try {
    if (cuentaId) localStorage.setItem(clave(usuarioId), cuentaId)
  } catch {
    /* sin almacenamiento: no pasa nada */
  }
}

export function leerUltimaCuenta(usuarioId) {
  try {
    return localStorage.getItem(clave(usuarioId)) || ''
  } catch {
    return ''
  }
}

/** Cuenta con la que abre «+»: la última usada si aún existe; si no, la primera. */
export function cuentaInicial(cuentas, ultimaId) {
  const lista = cuentas || []
  return (lista.find((c) => c.id === ultimaId) || lista[0])?.id || ''
}
