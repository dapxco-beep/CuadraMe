// Fecha y hora de un movimiento para identificarlo de un vistazo: «mié 8 oct · 4:30 p. m.».
// La hora SOLO se muestra cuando existe: los extractos y archivos traen 00:00 (o 12:00 de relleno) y
// ahí se muestra solo el día, sin inventar «12:00 a. m.».
const TIENE_ZONA = /(Z|[+-]\d{2}:?\d{2})$/

function aFecha(valor) {
  if (valor == null || valor === '') return null
  // «2026-10-08» solo con día se lee como medianoche local (no UTC, que lo corre un día atrás)
  const d = new Date(typeof valor === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(valor) ? `${valor}T00:00:00` : valor)
  return Number.isNaN(d.getTime()) ? null : d
}

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

// Día (AAAA-MM-DD) en el que cae un movimiento. Con zona (Z o ±hh:mm) se cuenta en hora de Colombia: un gasto de las
// 9 p. m. llega al servidor como el día siguiente en UTC, pero es del día de Bogotá. Sin zona se respeta la fecha tal cual.
export function claveDia(valor) {
  const d = aFecha(valor)
  if (!d) return ''
  if (typeof valor === 'string' && !TIENE_ZONA.test(valor) && /^d{4}-d{2}-d{2}/.test(valor)) return valor.slice(0, 10)
  const p = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(d)
  const g = (t) => p.find((x) => x.type === t)?.value
  return `${g('year')}-${g('month')}-${g('day')}`
}

/** «Hoy», «Ayer» o «8 de octubre», contando los días en hora de Colombia. */
export function etiquetaDia(valor, ahora = new Date()) {
  const k = claveDia(valor)
  if (!k) return ''
  if (k === claveDia(ahora.toISOString())) return 'Hoy'
  if (k === claveDia(new Date(ahora.getTime() - 86_400_000).toISOString())) return 'Ayer'
  return new Date(`${k}T12:00:00`).toLocaleDateString('es-CO', { day: 'numeric', month: 'long' })
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
