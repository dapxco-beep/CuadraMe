// Cola mínima para registrar un gasto SIN señal.
//
// Qué hace: si al guardar un movimiento no hay conexión (el navegador ni siquiera llegó al
// servidor), se guarda en el celular y se envía solo cuando vuelve la red.
// Por qué es de bajo riesgo:
//  - Solo se encolan movimientos nuevos (ingreso/gasto). Editar, borrar, transferir y todo lo
//    demás siguen pidiendo conexión: un cambio que pisa a otro es peor que un error claro.
//  - Si el servidor ya lo tenía (409 posible_duplicado: por ejemplo la respuesta se perdió pero el
//    movimiento sí se guardó), se descarta sin duplicar.
//  - Se envían uno por uno y en orden; ante el primer fallo de red se detiene y reintenta luego.
//  - Está separada por usuario y se borra al cerrar sesión.
const CLAVE = 'cuadrame:cola-movimientos'

function leer() {
  try {
    const crudo = window.localStorage.getItem(CLAVE)
    const lista = crudo ? JSON.parse(crudo) : []
    return Array.isArray(lista) ? lista : []
  } catch {
    return []
  }
}

function escribir(lista) {
  try {
    if (lista.length) window.localStorage.setItem(CLAVE, JSON.stringify(lista))
    else window.localStorage.removeItem(CLAVE)
    return true
  } catch {
    return false
  }
}

/** Fecha y hora local sin zona (AAAA-MM-DDTHH:mm:ss), como las que envía la app. */
export function ahoraLocalISO(d = new Date()) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

/** Guarda un movimiento para enviarlo después. Devuelve false si el celular no deja guardarlo. */
export function encolarMovimiento(usuarioId, datos) {
  if (!usuarioId) return false
  const lista = leer()
  lista.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    usuarioId,
    datos: { ...datos, fecha: datos.fecha || ahoraLocalISO() }, // la hora real del gasto, no la del envío
    en: Date.now(),
  })
  return escribir(lista)
}

export function pendientesDe(usuarioId) {
  return leer().filter((p) => p.usuarioId === usuarioId)
}

export function vaciarCola() {
  escribir([])
}

let enviando = false

/**
 * Envía lo pendiente de este usuario. Devuelve { enviados, descartados, quedan }.
 * `crear` es api.crearMovimiento (se inyecta para poder probarla).
 */
export async function enviarPendientes(usuarioId, crear) {
  const res = { enviados: 0, descartados: 0, quedan: 0 }
  if (enviando || !usuarioId) return res
  enviando = true
  try {
    for (const item of pendientesDe(usuarioId)) {
      try {
        await crear(item.datos)
        res.enviados++
      } catch (err) {
        if (err?.sinConexion || (err?.status ?? 0) >= 500 || err?.status === 401) break // se reintenta luego
        // Ya estaba registrado (409) o el servidor lo rechazó (datos inválidos): no se reintenta.
        res.descartados++
      }
      escribir(leer().filter((p) => p.id !== item.id))
    }
    res.quedan = pendientesDe(usuarioId).length
    return res
  } finally {
    enviando = false
  }
}
