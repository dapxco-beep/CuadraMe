import { aFecha } from './fechaLocal'
// Fecha y hora de un movimiento para identificarlo de un vistazo: «mié 8 oct · 4:30 p. m.».
// La hora SOLO se muestra cuando existe: los extractos y archivos traen 00:00 (o 12:00 de relleno) y
// ahí se muestra solo el día, sin inventar «12:00 a. m.».
const TIENE_ZONA = /(Z|[+-]\d{2}:?\d{2})$/


// Si el texto trae zona (Z o +hh:mm) se muestra en hora de Colombia; si es una fecha «de pared»
// (sin zona) se respeta tal cual, sin desplazarla.
function opciones(valor, base) {
  return typeof valor === 'string' && TIENE_ZONA.test(valor) ? { ...base, timeZone: 'America/Bogota' } : base
}

function partes(valor) {
  const d = aFecha(valor)
  if (!d) return null
  const hm = new Intl.DateTimeFormat('es-CO', opciones(valor, { hour: 'numeric', minute: '2-digit', hourCycle: 'h23' })).formatToParts(d)
  const h = Number(hm.find((p) => p.type === 'hour')?.value)
  const mi = Number(hm.find((p) => p.type === 'minute')?.value)
  return { d, h, mi }
}

export function tieneHora(valor) {
  const p = partes(valor)
  if (!p) return false
  return !(p.mi === 0 && (p.h === 0 || p.h === 12) && p.d.getSeconds() === 0)
}

export function diaCorto(valor, { anio = false } = {}) {
  const d = aFecha(valor)
  if (!d) return ''
  const t = new Intl.DateTimeFormat('es-CO', opciones(valor, { weekday: 'short', day: 'numeric', month: 'short', ...(anio ? { year: 'numeric' } : {}) })).format(d)
  return t.replace(/\./g, '').replace(',', '').replace(/ de /g, ' ')
}

export function horaCorta(valor) {
  const d = aFecha(valor)
  if (!d || !tieneHora(valor)) return ''
  return new Intl.DateTimeFormat('es-CO', opciones(valor, { hour: 'numeric', minute: '2-digit' })).format(d)
}

/** «mié 8 oct · 4:30 p. m.» (o «mié 8 oct» si no hay hora real). */
export function fechaHoraMovimiento(valor, opts) {
  const dia = diaCorto(valor, opts)
  if (!dia) return ''
  const h = horaCorta(valor)
  return h ? `${dia} · ${h}` : dia
}

/** Fecha de un movimiento: la del correo si vino de uno (trae la hora del aviso), si no la propia. */
export function fechaDeMovimiento(m) {
  return m?.fecha_movimiento || m?.fecha
}
