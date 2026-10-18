import { api } from './api'

// La sincronización de Gmail es por lotes: cada llamada lee unos 40 correos y
// devuelve el progreso. Aquí se repite hasta que `completado` sea true. Si se
// corta (cierras la app, se cae la red), la siguiente llamada sigue donde quedó.
// Una respuesta sin `completado` (servidor viejo) cuenta como terminada.
export async function sincronizarTodo({ completa = false, tipo = 'todo', dias, releer = false, onProgreso, maxLlamadas = 80 } = {}) {
  let r = null
  for (let i = 0; i < maxLlamadas; i++) {
    const params = { ...(completa && i === 0 ? { completa: true, ...(dias ? { dias } : {}), ...(releer ? { releer: true } : {}) } : {}), ...(tipo !== 'todo' ? { tipo } : {}) }
    r = await api.sincronizarCorreos(Object.keys(params).length ? params : undefined)
    if (!r?.ok) return r
    onProgreso?.(r)
    if (r.completado !== false) return r
  }
  return r
}

// «Traer todo»: cada uso del correo corre POR SEPARADO (primero movimientos, luego extractos) y cada uno
// devuelve su propio resultado o error: si uno falla, el otro igual se lee. `activos` = lo que el usuario
// dejó encendido. Devuelve { movimientos?: {r}|{error}, extractos?: ... }; un carril apagado no aparece.
export async function sincronizarCarriles({ activos = {}, completa = false, onProgreso } = {}) {
  const salida = {}
  for (const tipo of ['movimientos', 'extractos']) {
    if (activos[tipo] === false) continue
    try {
      const r = await sincronizarTodo({ completa, tipo, onProgreso: (p) => onProgreso?.(tipo, p) })
      salida[tipo] = r?.ok ? { r } : { error: r?.error || 'No se pudo leer. Intenta de nuevo.' }
    } catch (err) {
      salida[tipo] = { error: err?.message || 'No se pudo leer. Intenta de nuevo.' }
    }
  }
  return salida
}

// Sincronización automática al abrir el centro: como máximo cada 6 horas, con el mismo
// endpoint del botón (no hay cron nuevo). La marca vive en localStorage (con try/catch).
export const CLAVE_SYNC = 'cuadrame_gmail_sync'
const SEIS_HORAS = 6 * 60 * 60 * 1000

export function tocaSincronizar(cadaMs = SEIS_HORAS) {
  try {
    return Date.now() - Number(localStorage.getItem(CLAVE_SYNC) || 0) > cadaMs
  } catch {
    return false
  }
}

export function marcarSincronizado() {
  try {
    localStorage.setItem(CLAVE_SYNC, String(Date.now()))
  } catch {
    /* sin almacenamiento: se sincroniza solo a mano */
  }
}

// "hace 2 h" a partir de una fecha ISO del servidor (UTC sin zona).
export function haceCuanto(iso, ahora = Date.now()) {
  if (!iso) return null
  const t = Date.parse(/(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`)
  if (Number.isNaN(t)) return null
  const min = Math.max(0, Math.round((ahora - t) / 60000))
  if (min < 1) return 'hace un momento'
  if (min < 60) return `hace ${min} min`
  const h = Math.round(min / 60)
  if (h < 24) return `hace ${h} h`
  const d = Math.round(h / 24)
  return d === 1 ? 'hace 1 día' : `hace ${d} días`
}

// Resumen en una frase de lo que pasó al sincronizar.
export function resumenSync(r) {
  const nuevos = r?.nuevos || 0
  const ext = r?.extractos_encontrados ?? r?.extractos_nuevos ?? 0
  if (!nuevos && !ext) return 'No hay nada nuevo en tu correo.'
  const partes = []
  if (nuevos) partes.push(`${nuevos} movimiento${nuevos === 1 ? '' : 's'} nuevo${nuevos === 1 ? '' : 's'}`)
  if (ext) partes.push(`${ext} extracto${ext === 1 ? '' : 's'}`)
  return `Encontré ${partes.join(' y ')}.`
}

// ── Movimientos «en vivo» ───────────────────────────────────────────────────────────────────
// Lectura ligera de las notificaciones del banco (carril «movimientos», sin extractos) al abrir Movimientos,
// al volver a la app y con el botón «Actualizar desde el correo». Reutiliza el endpoint de siempre y la
// MISMA marca que «Traer movimientos» (CLAVE_SYNC): si una acaba de correr, la otra no repite.
export const CINCO_MIN = 5 * 60 * 1000

// Frase corta para el aviso: «Traje 2 movimientos nuevos» / «Todo al día».
export function resumenActualizacion(r) {
  const n = r?.nuevos || 0
  if (!n) return 'No hay nada nuevo en tu correo.'
  return `Traje ${n} movimiento${n === 1 ? '' : 's'} nuevo${n === 1 ? '' : 's'}`
}

/**
 * Devuelve { nuevos, omitido } y nunca lanza. `manual` ignora el límite de 5 min. `conectado === false`
 * (Gmail sin conectar) no llama a nada. Máximo 3 lotes por actualización (unos 120 correos): lo que falte
 * lo sigue la próxima, que retoma el cursor del servidor.
 */
export async function actualizarDesdeCorreo({ manual = false, conectado = true, cadaMs = CINCO_MIN } = {}) {
  if (!conectado) return { nuevos: 0, omitido: true }
  if (!manual && !tocaSincronizar(cadaMs)) return { nuevos: 0, omitido: true }
  try {
    const r = await sincronizarTodo({ tipo: 'movimientos', maxLlamadas: 3 })
    if (!r?.ok) return { nuevos: 0, error: r?.error || 'No se pudo leer tu correo.' }
    marcarSincronizado()
    return { nuevos: r.nuevos || 0 }
  } catch (err) {
    return { nuevos: 0, error: err?.message || 'No se pudo leer tu correo.' }
  }
}
