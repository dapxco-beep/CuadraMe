// Lógica pura (sin React) de la bandeja "¿son tuyos?" y de la pregunta "¿hiciste
// algún movimiento?". Separada de los componentes para poder probarla fácil.
//
// Todo lo que se guarda en localStorage va en try/catch: en modo privado, con
// datos bloqueados o en vistas previas puede lanzar, y la app debe seguir andando.

export const CLAVE_BANDEJA = 'cuadrame.bandeja.cerrada'
export const CLAVE_PREGUNTA = 'cuadrame.pregunta.oculta'
export const HORA_SIN_MOLESTAR = 60 * 60 * 1000 // 1 hora tras cerrar la bandeja
export const HORAS_SIN_MOVIMIENTO = 6 // pregunta si pasaron más de 6 horas desde el último
export const HORA_MINIMA_PREGUNTA = 9 // no se pregunta de madrugada

function leer(clave) {
  try {
    const bruto = window.localStorage.getItem(clave)
    return bruto ? JSON.parse(bruto) : null
  } catch {
    return null
  }
}

function escribir(clave, valor) {
  try {
    window.localStorage.setItem(clave, JSON.stringify(valor))
  } catch {
    /* sin almacenamiento: se pierde solo la memoria de "ya la cerré" */
  }
}

/**
 * Decide si se muestra la bandeja. `estado` es lo que se guardó al cerrarla:
 * { ts, ids } (cuándo y qué movimientos había). No vuelve a salir durante una
 * hora salvo que haya movimientos nuevos que no estaban cuando la cerró.
 */
export function debeMostrarBandeja(pendientes, estado, ahora = Date.now()) {
  if (!pendientes || pendientes.length === 0) return false
  if (!estado || !estado.ts) return true
  const hayNuevos = pendientes.some((m) => !(estado.ids || []).includes(m.id))
  if (hayNuevos) return true
  return ahora - estado.ts >= HORA_SIN_MOLESTAR
}

export function estadoBandejaGuardado() {
  return leer(CLAVE_BANDEJA)
}

/** Guarda "la cerré ahora" junto con los ids que había, para detectar nuevos. */
export function recordarBandejaCerrada(pendientes, ahora = Date.now()) {
  escribir(CLAVE_BANDEJA, { ts: ahora, ids: (pendientes || []).map((m) => m.id) })
}

// --- Pregunta "¿hiciste algún movimiento?" ---------------------------------

export function fechaLocalISO(d = new Date()) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dia}`
}

/** "AAAA-MM-DDTHH:MM:SS" (hora de Colombia, sin zona) -> Date local. */
export function fechaDeMovimiento(texto) {
  if (!texto) return null
  const d = new Date(String(texto).replace(' ', 'T').replace(/Z$|[+-]\d\d:?\d\d$/, ''))
  return Number.isNaN(d.getTime()) ? null : d
}

export function preguntaOcultaHoy(ahora = new Date()) {
  const guardada = leer(CLAVE_PREGUNTA)
  return guardada === fechaLocalISO(ahora)
}

/** "No hice ninguno": la oculta hasta mañana. */
export function ocultarPreguntaHoy(ahora = new Date()) {
  escribir(CLAVE_PREGUNTA, fechaLocalISO(ahora))
}

/**
 * Se pregunta si ya pasó la hora mínima del día y: hoy no hay movimientos, o
 * pasaron `HORAS_SIN_MOVIMIENTO` horas desde el último. `ultimaFecha` es la
 * fecha del movimiento más reciente (o null si no hay ninguno).
 */
export function debePreguntarMovimiento({ ultimaFecha, ahora = new Date(), oculta = false }) {
  if (oculta) return false
  if (ahora.getHours() < HORA_MINIMA_PREGUNTA) return false
  const ultima = ultimaFecha instanceof Date ? ultimaFecha : fechaDeMovimiento(ultimaFecha)
  if (!ultima) return true
  if (fechaLocalISO(ultima) !== fechaLocalISO(ahora)) return true // hoy no hay movimientos
  return ahora.getTime() - ultima.getTime() >= HORAS_SIN_MOVIMIENTO * 60 * 60 * 1000
}

// --- Aviso entre la bandeja y la pregunta (la pregunta espera a que cierre) --

let abierta = false
export function bandejaAbierta() {
  return abierta
}
export function marcarBandejaAbierta(valor) {
  abierta = !!valor
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('cuadrame:bandeja', { detail: { abierta } }))
}
