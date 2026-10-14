// Fechas de los movimientos que llegan por correo. El servidor las manda en hora de Colombia, sin zona
// («2026-10-08T16:30:00»): aquí se leen por partes (nunca con new Date(texto)) para que no se corran
// según la zona del celular.

const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb']
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

/** «2026-10-08T16:30:00» -> { a, m, d, h, mi } (m de 1 a 12). null si no se entiende. */
export function partesFecha(iso) {
  const r = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(String(iso || ''))
  if (!r) return null
  return { a: +r[1], m: +r[2], d: +r[3], h: r[4] ? +r[4] : 0, mi: r[5] ? +r[5] : 0 }
}

const diaSemana = (p) => DIAS[new Date(Date.UTC(p.a, p.m - 1, p.d)).getUTCDay()]
const dosDig = (n) => String(n).padStart(2, '0')

export const horaBonita = (p) => `${p.h % 12 || 12}:${dosDig(p.mi)} ${p.h < 12 ? 'am' : 'pm'}`

/** «Mar 8 oct 2026 · 4:30 pm» (sin la hora si el correo no la trae). */
export function etiquetaFechaHora(iso, conHora = true) {
  const p = partesFecha(iso)
  if (!p) return ''
  const dia = diaSemana(p)
  const base = `${dia[0].toUpperCase()}${dia.slice(1)} ${p.d} ${MESES[p.m - 1]} ${p.a}`
  return conHora ? `${base} · ${horaBonita(p)}` : base
}

/** Llave del día para agrupar: «2026-10-08». */
export const claveDia = (iso) => String(iso || '').slice(0, 10)

/** «Hoy», «Ayer» o «8 oct» (con el año si no es el actual). `hoy` es un Date (por defecto, ahora). */
export function etiquetaDia(iso, hoy = new Date()) {
  const p = partesFecha(iso)
  if (!p) return 'Sin fecha'
  const clave = (y, m, d) => `${y}-${dosDig(m)}-${dosDig(d)}`
  const h = clave(hoy.getFullYear(), hoy.getMonth() + 1, hoy.getDate())
  const ay = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - 1)
  const a = clave(ay.getFullYear(), ay.getMonth() + 1, ay.getDate())
  const c = clave(p.a, p.m, p.d)
  if (c === h) return 'Hoy'
  if (c === a) return 'Ayer'
  return `${p.d} ${MESES[p.m - 1]}${p.a === hoy.getFullYear() ? '' : ` ${p.a}`}`
}

/** Valor para <input type="date">: «2026-10-08». */
export const valorInputFecha = (iso) => claveDia(iso)

/** Fecha que se manda al aprobar: el día elegido con la hora que ya tenía el movimiento. */
export function fechaParaEnviar(dia, iso) {
  const p = partesFecha(iso)
  const hora = p ? `${dosDig(p.h)}:${dosDig(p.mi)}:00` : '00:00:00'
  return `${dia}T${hora}`
}

/** True si el movimiento y la llegada del correo difieren en más de una hora (vale la pena decirlo). */
export function fechasDistintas(iso, otroIso) {
  const a = partesFecha(iso)
  const b = partesFecha(otroIso)
  if (!a || !b) return false
  const ms = (p) => Date.UTC(p.a, p.m - 1, p.d, p.h, p.mi)
  return Math.abs(ms(a) - ms(b)) > 60 * 60 * 1000
}

/** Agrupa tarjetas (ya ordenadas) por día del movimiento: [{ clave, etiqueta, items }]. */
export function agruparPorDia(correos, hoy = new Date()) {
  const grupos = []
  // Lo más reciente primero (el servidor ya lo manda así; esto protege de cualquier otro orden).
  const ordenados = [...(correos || [])].sort((x, y) => String(y.fecha_movimiento || '').localeCompare(String(x.fecha_movimiento || '')))
  for (const c of ordenados) {
    const clave = claveDia(c.fecha_movimiento || c.recibido_en_co) || 'sin-fecha'
    let g = grupos.find((x) => x.clave === clave)
    if (!g) {
      g = { clave, etiqueta: etiquetaDia(c.fecha_movimiento || c.recibido_en_co, hoy), items: [] }
      grupos.push(g)
    }
    g.items.push(c)
  }
  return grupos
}
