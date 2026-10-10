// «Tu opinión cuenta»: tipos, textos y utilidades del buzón. Sin React.
//
// Privacidad: solo se envía el texto que la persona escribe, la RUTA de la pantalla (sin parámetros)
// y un resumen corto del dispositivo («móvil · Chrome»). Nunca saldos, movimientos ni cuentas.

export const MAX_MENSAJE = 2000

// id = valor que entiende el servidor
export const TIPOS = [
  { id: 'sugerencia', emoji: '💡', etiqueta: 'Una idea', pista: '¿Qué te gustaría que hiciera CuadraMe?' },
  { id: 'problema', emoji: '🐞', etiqueta: 'Algo falló', pista: '¿Qué estabas haciendo y qué pasó?' },
  { id: 'pregunta', emoji: '❓', etiqueta: 'Una duda', pista: '¿Qué no se entiende?' },
  { id: 'elogio', emoji: '💛', etiqueta: 'Algo me gustó', pista: '¡Cuéntanos qué te gustó!' },
]
const IDS_TIPO = TIPOS.map((t) => t.id)

// «Mi banco no aparece» no se elige en «Tu opinión cuenta»: nace del formulario de Traer movimientos.
// Aparece en el panel de administración (filtro «Bancos») y en la lista de comentarios de quien lo envió.
export const TIPO_BANCO = { id: 'banco', emoji: '🏦', etiqueta: 'Mi banco no aparece', corta: 'Bancos', pista: '' }
export const TIPOS_PANEL = [...TIPOS, TIPO_BANCO]

export const tipoPorId = (id) => TIPOS_PANEL.find((t) => t.id === id) || TIPOS[0]

// Del enlace (?tipo=problema) solo se aceptan los tipos conocidos.
export function tipoInicial(valor) {
  return IDS_TIPO.includes(valor) ? valor : 'sugerencia'
}

// ?desde=/movimientos?mes=2026-01 -> '/movimientos' (solo la ruta, sin datos en la query).
export function limpiarDesde(valor) {
  const ruta = String(valor || '').split('?')[0].split('#')[0]
  return /^\/[\w\-./]{0,118}$/.test(ruta) ? ruta : ''
}

// Ruta actual de la app (HashRouter): '#/movimientos?x=1' -> '/movimientos'.
export function rutaActual() {
  if (typeof window === 'undefined') return ''
  return limpiarDesde(String(window.location.hash || '').replace(/^#/, ''))
}

export function resumenDispositivo() {
  if (typeof navigator === 'undefined') return ''
  const ua = navigator.userAgent || ''
  const movil = /Android|iPhone|iPad|iPod|Mobile/i.test(ua)
  let navegador = 'otro navegador'
  if (/Edg\//.test(ua)) navegador = 'Edge'
  else if (/OPR\//.test(ua)) navegador = 'Opera'
  else if (/Firefox\//.test(ua)) navegador = 'Firefox'
  else if (/Chrome\/|CriOS\//.test(ua)) navegador = 'Chrome'
  else if (/Safari\//.test(ua)) navegador = 'Safari'
  let instalada = false
  try {
    instalada = window.matchMedia?.('(display-mode: standalone)')?.matches || navigator.standalone === true
  } catch {
    instalada = false
  }
  return [movil ? 'móvil' : 'escritorio', navegador, instalada ? 'app instalada' : null].filter(Boolean).join(' · ')
}

export const VERSION_APP = String(import.meta.env.VITE_APP_VERSION || '').slice(0, 40)

// ── Panel de administración ──
export const ESTADOS_ADMIN = [
  { id: 'nuevo', etiqueta: 'Nuevo' },
  { id: 'visto', etiqueta: 'Visto' },
  { id: 'en_curso', etiqueta: 'En curso' },
  { id: 'resuelto', etiqueta: 'Resuelto' },
  { id: 'descartado', etiqueta: 'Descartado' },
]

export const etiquetaEstado = (id) => ESTADOS_ADMIN.find((e) => e.id === id)?.etiqueta || id

export function fechaCorta(iso) {
  if (!iso) return ''
  const d = new Date(String(iso).endsWith('Z') ? iso : `${iso}Z`)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('es-CO', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
