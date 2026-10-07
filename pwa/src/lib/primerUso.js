// Reglas puras del asistente de primer uso («Primeros pasos»): qué pasos hay, cuál está hecho
// según el estado REAL de la cuenta, y qué recuerda el celular (ocultar, saltar). Sin React.

export const CLAVE_ESTADO = 'cuadrame:primeros-pasos'

/** 'ios' | 'android' | 'otro'. El iPad moderno se presenta como Mac con pantalla táctil. */
export function detectarDispositivo(ua = typeof navigator !== 'undefined' ? navigator.userAgent : '', maxTouch = typeof navigator !== 'undefined' ? navigator.maxTouchPoints || 0 : 0) {
  if (/iPhone|iPad|iPod/i.test(ua)) return 'ios'
  if (/Macintosh/i.test(ua) && maxTouch > 1) return 'ios'
  if (/Android/i.test(ua)) return 'android'
  return 'otro'
}

/** ¿La app corre ya desde el ícono de la pantalla de inicio (no desde una pestaña del navegador)? */
export function estaInstalada() {
  if (typeof window === 'undefined') return false
  try {
    if (window.navigator?.standalone === true) return true
    return !!window.matchMedia?.('(display-mode: standalone)')?.matches
  } catch {
    return false
  }
}

// Orden pensado para alguien que llega por primera vez: lo básico primero, lo automático después.
export const PASOS = [
  {
    id: 'cuentas',
    titulo: 'Crea tus cuentas',
    apoyo: 'Efectivo, Nequi, tu banco… las que uses a diario.',
    ruta: '/cuentas',
    accion: 'Ver mis cuentas',
  },
  {
    id: 'instalar',
    titulo: 'Ponla en tu celular',
    apoyo: 'Con un ícono en la pantalla de inicio se abre como cualquier app.',
    accion: 'Ver cómo',
    guia: 'instalar',
  },
  {
    id: 'notificaciones',
    titulo: 'Activa los avisos',
    apoyo: 'Te avisamos cuando te acerques al límite de un presupuesto o se registre un pago.',
    ruta: '/perfil',
    accion: 'Activar avisos',
    activable: true,
  },
  {
    id: 'gmail',
    titulo: 'Conecta tu Gmail',
    apoyo: 'Para que los avisos de tu banco se conviertan en movimientos sin escribir nada.',
    ruta: '/correos',
    accion: 'Conectar Gmail',
    privacidad: true,
  },
  {
    id: 'atajo',
    titulo: 'Registra tus pagos con Apple Pay',
    apoyo: 'Cada pago con tu iPhone queda anotado solo. Toma unos 3 minutos.',
    ruta: '/conectar-dispositivo',
    accion: 'Instalar el atajo',
    solo: 'ios',
  },
  {
    id: 'extracto',
    titulo: 'Sube tu primer extracto',
    apoyo: 'El PDF que te manda tu banco: lo comparamos con lo que registraste.',
    ruta: '/sincronizacion',
    accion: 'Subir un extracto',
  },
]

/**
 * Pasos que le corresponden a este dispositivo, cada uno con `hecho` calculado del estado real.
 *   datos: { cuentas, instalada, permisoPush, pushActivo, gmailConectado, atajoUsado, hayExtracto }
 *   saltados: ids que la persona decidió dejar para después (cuentan como resueltos)
 */
export function armarPasos({ dispositivo = 'otro', datos = {}, saltados = [] } = {}) {
  const hechoDe = {
    cuentas: (datos.cuentas || 0) >= 1,
    instalar: !!datos.instalada,
    notificaciones: datos.permisoPush === 'granted' || !!datos.pushActivo,
    gmail: !!datos.gmailConectado,
    atajo: !!datos.atajoUsado,
    extracto: !!datos.hayExtracto,
  }
  return PASOS.filter((p) => !p.solo || p.solo === dispositivo).map((p) => {
    const hecho = !!hechoDe[p.id]
    const saltado = !hecho && saltados.includes(p.id)
    return { ...p, hecho, saltado, resuelto: hecho || saltado }
  })
}

export function resumenProgreso(pasos) {
  const total = pasos.length
  const resueltos = pasos.filter((p) => p.resuelto).length
  const hechos = pasos.filter((p) => p.hecho).length
  return { total, resueltos, hechos, completo: total > 0 && resueltos === total, pct: total ? Math.round((resueltos / total) * 100) : 0 }
}

/** Primer paso pendiente: el que se destaca como «sigue este». */
export const siguientePaso = (pasos) => pasos.find((p) => !p.resuelto) || null

// ── Memoria del celular (solo conveniencia: si no hay almacenamiento, todo funciona igual) ──
const VACIO = { oculto: false, saltados: [] }

export function leerEstado(uid = 'anon') {
  try {
    const todo = JSON.parse(localStorage.getItem(CLAVE_ESTADO) || '{}')
    const e = todo?.[uid]
    return { oculto: !!e?.oculto, saltados: Array.isArray(e?.saltados) ? e.saltados : [] }
  } catch {
    return { ...VACIO }
  }
}

export function guardarEstado(uid = 'anon', estado) {
  try {
    const todo = JSON.parse(localStorage.getItem(CLAVE_ESTADO) || '{}')
    localStorage.setItem(CLAVE_ESTADO, JSON.stringify({ ...todo, [uid]: estado }))
  } catch {
    /* sin almacenamiento: no se recuerda */
  }
}
