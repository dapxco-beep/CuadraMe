// Reglas puras del centro "Traer movimientos" (/sincronizacion): qué tarea va en qué bloque,
// el contador total y a dónde llevan las rutas viejas. Sin React, fáciles de probar.

export const RUTA_CENTRO = '/sincronizacion'

// Los tres bloques del centro.
export const BLOQUES = ['correo', 'subir', 'revisar']

// Cada tarea de GET /sincronizacion/estado vive en un solo bloque.
const BLOQUE_DE_TAREA = {
  correos_por_revisar: 'correo',
  extractos_por_conciliar: 'correo',
  falta_clave: 'correo',
  movimientos_por_confirmar: 'revisar',
  movimientos_por_categorizar: 'revisar',
  sin_cuenta: 'revisar',
}

export const bloqueDeTarea = (id) => BLOQUE_DE_TAREA[id] || 'revisar'

export const tareasDeBloque = (tareas, bloque) => (tareas || []).filter((t) => bloqueDeTarea(t.id) === bloque)

// UN solo contador de "cosas por resolver": el mismo número que muestra Inicio
// (cantidad de tareas pendientes de GET /sincronizacion/estado). Los contadores de cada
// bloque suman exactamente este total.
export const totalPorResolver = (tareas) => (tareas || []).length

export const cantidadDe = (tareas, id) => (tareas || []).find((t) => t.id === id)?.cantidad || 0

// Rutas viejas -> dónde abrir el centro. `abrir` es el bloque (o 'estado' para la hoja de
// conexiones); el resto del state (historialId, cuentaId, mes) lo entiende el bloque.
const DESTINOS = {
  '/correos': { abrir: 'correo' },
  '/conciliacion': { abrir: 'subir' },
  '/importar': { abrir: 'subir', manual: true },
  '/conexiones': { abrir: 'estado' },
}

export const RUTAS_VIEJAS = Object.keys(DESTINOS)

/** { to, state } para redirigir una ruta vieja; conserva la query (?gmail=sin_acceso...) y el state que traía. */
export function destinoRedireccion(ruta, location = {}) {
  const base = DESTINOS[ruta] || { abrir: 'revisar' }
  return {
    to: `${RUTA_CENTRO}${location.search || ''}`,
    state: { ...(location.state || {}), ...base },
  }
}

// Barra de pasos Conecta -> Trae -> Revisa.
export const PASOS = ['Conecta', 'Trae', 'Revisa']

/** Sin nada que mostrar todavía: Gmail sin conectar o sin sincronizar, cuadrícula vacía y sin tareas. */
export function sinDatos({ estado, conectado }) {
  if (!estado) return false
  const hayCeldas = (estado.cuentas || []).some((c) => (c.meses || []).some((m) => m.estado !== 'vacio'))
  if (hayCeldas || (estado.tareas || []).length > 0) return false
  return !conectado || !estado.ultima_sync
}

/**
 * Monto escrito a mano -> número. Acepta '12500', '12.500', '12,500' y '12.500,50'/'12,500.50'.
 * Un solo separador seguido de exactamente 3 dígitos es de miles ('12.500'); si no, decimal.
 * Devuelve 0 si no se entiende (el botón de aprobar sigue deshabilitado).
 */
export function parsearMontoEscrito(texto) {
  const s = String(texto ?? '').replace(/[^\d.,]/g, '')
  if (!s) return 0
  const ultimoPunto = s.lastIndexOf('.')
  const ultimaComa = s.lastIndexOf(',')
  const sep = Math.max(ultimoPunto, ultimaComa)
  let n
  if (sep < 0) n = Number(s)
  else {
    const separadores = (s.match(/[.,]/g) || []).length
    const decimales = s.length - sep - 1
    const esMiles = separadores > 1 ? new Set(s.match(/[.,]/g)).size === 1 : decimales === 3
    n = esMiles ? Number(s.replace(/[.,]/g, '')) : Number(`${s.slice(0, sep).replace(/[.,]/g, '')}.${s.slice(sep + 1)}`)
  }
  return Number.isFinite(n) && n > 0 ? n : 0
}

/** Paso en el que va el usuario (1 conectar, 2 traer, 3 revisar). */
export function pasoActual({ conectado, tareas }) {
  if (!conectado) return 1
  return (tareas || []).length > 0 ? 3 : 2
}

