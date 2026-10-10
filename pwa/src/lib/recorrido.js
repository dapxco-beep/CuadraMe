// Reglas puras del recorrido guiado («tour») que ve quien entra a una cuenta nueva: qué pasos hay,
// qué recuerda el celular (avance, saltado, terminado) y cuándo se abre solo. Sin React.
//
// Pensado para gente que no es técnica: 4 tarjetas, 1–2 frases, una ilustración y un botón
// «Probar ahora» que lleva a esa pantalla. Si la persona sale, retoma donde iba desde Perfil o Ayuda.

export const CLAVE_RECORRIDO = 'cuadrame:recorrido'

export const PASOS_RECORRIDO = [
  {
    id: 'inicio',
    area: 'Qué es',
    titulo: 'Te muestra a dónde se va tu plata',
    texto:
      'Anotas lo que entra y lo que sale, y CuadraMe te dice cuánta plata tienes y en qué la gastas. Sin hojas de cálculo.',
    ruta: '/',
    accion: 'Ir a Inicio',
  },
  {
    id: 'traer',
    area: 'Tus movimientos',
    titulo: 'Los movimientos llegan sin escribirlos',
    texto:
      'Usa el correo de tu banco, el extracto en PDF o un Excel. También puedes anotar uno a mano. Elige lo que te quede más fácil.',
    detalle:
      'Correo: ideal para empezar, sin escribir nada. Extracto: lo más exacto, lo comparamos con lo que ya anotaste. Excel: para traer de una vez un historial viejo. Atajo de Apple Pay: solo iPhone y es opcional; anota cada pago al instante.',
    ruta: '/sincronizacion',
    accion: 'Traer movimientos',
  },
  {
    id: 'informes',
    area: 'Tu plata',
    titulo: 'Mira en qué gastas más',
    texto:
      'Cada gasto tiene un tipo (comida, transporte…). Así ves cuánto se va en cada cosa y puedes ponerte un límite al mes.',
    detalle:
      'Si pasas plata de una cuenta tuya a otra (de tu banco a Nequi), no es un gasto ni un ingreso: la plata sigue siendo tuya, y no cuenta en tus informes.',
    ruta: '/informe',
    accion: 'Ver mi resumen',
  },
  {
    id: 'privacidad',
    area: 'Privacidad',
    titulo: 'Tus datos son tuyos',
    texto:
      'Del correo solo leemos los avisos de tu banco. No leemos tus correos personales, no enviamos ni borramos nada y puedes quitar el permiso cuando quieras.',
    ruta: '/ayuda?p=gmail-seguro',
    accion: 'Leer más',
  },
]

export const TOTAL_PASOS = PASOS_RECORRIDO.length

/** Ruta de «Probar ahora» de un paso (con '/' para Inicio). */
export const rutaDelPaso = (indice) => PASOS_RECORRIDO[acotar(indice)]?.ruta || '/'

export function acotar(indice) {
  const n = Number.isFinite(indice) ? Math.trunc(indice) : 0
  return Math.max(0, Math.min(TOTAL_PASOS - 1, n))
}

/** Avance 0–100 mostrado en la barra (paso actual sobre el total). */
export const porcentajeRecorrido = (indice) => Math.round(((acotar(indice) + 1) / TOTAL_PASOS) * 100)

// ── Memoria del celular (solo conveniencia: sin almacenamiento todo funciona igual) ──
//   paso: índice donde se quedó · terminado/saltado: ya no se abre solo · pendiente: abrir al entrar
const VACIO = { paso: 0, terminado: false, saltado: false, pendiente: false, empezado: false }

export function leerRecorrido(uid = 'anon') {
  try {
    const todo = JSON.parse(localStorage.getItem(CLAVE_RECORRIDO) || '{}')
    const e = todo?.[uid] || {}
    return {
      paso: acotar(e.paso),
      terminado: !!e.terminado,
      saltado: !!e.saltado,
      pendiente: !!e.pendiente,
      empezado: !!e.empezado,
    }
  } catch {
    return { ...VACIO }
  }
}

export function guardarRecorrido(uid = 'anon', cambios = {}) {
  const actual = leerRecorrido(uid)
  const siguiente = { ...actual, ...cambios, paso: acotar(cambios.paso ?? actual.paso) }
  try {
    const todo = JSON.parse(localStorage.getItem(CLAVE_RECORRIDO) || '{}')
    localStorage.setItem(CLAVE_RECORRIDO, JSON.stringify({ ...todo, [uid]: siguiente }))
  } catch {
    /* sin almacenamiento: no se recuerda */
  }
  return siguiente
}

/** Al crear la primera cuenta: el recorrido se abrirá solo la primera vez que se entre a Inicio. */
export const marcarRecorridoPendiente = (uid = 'anon') => guardarRecorrido(uid, { pendiente: true, terminado: false, saltado: false, paso: 0 })

/**
 * El recorrido es OPCIONAL («Conoce CuadraMe en 1 minuto»): nunca se abre solo. Quien llega lo primero
 * que ve es el camino de 3 pasos de Inicio. (Se conserva la función por si algo la importa.)
 */
export const debeAbrirseSolo = () => false

/** ¿Hay un recorrido a medias que se pueda retomar? */
export const sePuedeRetomar = (e) => !!e?.empezado && !e.terminado && !e.saltado && !e.pendiente
