// Fechas en la zona del dispositivo (Colombia, UTC-5, para casi todas las personas).
// Por qué existe: `new Date().toISOString().slice(0, 10)` da la fecha en UTC, y desde las 7 p. m. en
// Colombia ya es «mañana». Y `new Date('2026-10-08')` (solo día) se lee como medianoche UTC, o sea el
// 7 de octubre a las 7 p. m. Aquí vive la forma correcta de ambas cosas, para usarla en toda la app.

/** Fecha o texto -> Date. Un «AAAA-MM-DD» solo con día se lee como medianoche LOCAL. null si no se entiende. */
export function aFecha(valor) {
  if (valor == null || valor === '') return null
  const d = new Date(typeof valor === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(valor) ? `${valor}T00:00:00` : valor)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Milisegundos de una fecha (con la regla de «solo día» de aFecha); NaN si no se entiende. */
export function msFecha(valor) {
  const d = aFecha(valor)
  return d ? d.getTime() : NaN
}

/** Date -> «AAAA-MM-DD» según el calendario local (no UTC). */
export function fechaLocalISO(d = new Date()) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dia}`
}

/** El día de hoy como «AAAA-MM-DD», en hora local. */
export function hoyISO() {
  return fechaLocalISO(new Date())
}
