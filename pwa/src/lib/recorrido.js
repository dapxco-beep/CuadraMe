// Reglas puras del recorrido guiado («tour») que ve quien entra a una cuenta nueva: qué pasos hay,
// qué recuerda el celular (avance, saltado, terminado) y cuándo se abre solo. Sin React.
//
// Pensado para gente que no es técnica: un paso por área, 1–2 frases, una ilustración y un botón
// «Probar ahora» que lleva a esa pantalla. Si la persona sale, retoma donde iba desde Perfil o Ayuda.

export const CLAVE_RECORRIDO = 'cuadrame:recorrido'

export const PASOS_RECORRIDO = [
  {
    id: 'inicio',
    area: 'Inicio',
    titulo: 'Tu plata de un vistazo',
    texto:
      'Arriba ves cuánta plata tienes hoy. «Disponible» es lo que hay en tus cuentas de ahorros y efectivo, listo para gastar: no cuenta tus tarjetas de crédito.',
    ruta: '/',
    accion: 'Ir a Inicio',
  },
  {
    id: 'cuentas',
    area: 'Cuentas',
    titulo: 'Cuentas: débito o tarjeta',
    texto:
      'Una cuenta de ahorros o débito es plata que ya tienes: lo que pagas baja tu saldo. Una tarjeta de crédito es plata del banco: lo que compras es deuda, por eso la tarjeta resta.',
    detalle:
      'Ejemplo con Nu: tu cuenta de ahorros Nu tiene $500.000. Tu tarjeta de crédito Nu tiene un cupo de $2.000.000 y llevas $300.000 gastados: debes $300.000 y aún puedes gastar $1.700.000. El corte es el día en que el banco cierra tu cuenta del mes; el pago es la fecha límite para no pagar intereses.',
    ruta: '/cuentas',
    accion: 'Ver mis cuentas',
  },
  {
    id: 'traer',
    area: 'Traer movimientos',
    titulo: 'Que los movimientos lleguen solos',
    texto:
      'Elige lo que más te sirva: tu correo (avisos del banco), el extracto en PDF, un Excel, o el atajo de Apple Pay en iPhone para anotar cada pago al instante.',
    detalle:
      'Correo: ideal para empezar, sin escribir nada. Extracto: lo más exacto, lo cruzamos con lo que ya registraste. Excel: para traer un historial viejo de una vez. Atajo de Apple Pay: solo iPhone, anota el pago en el momento.',
    ruta: '/sincronizacion',
    accion: 'Traer movimientos',
  },
  {
    id: 'movimientos',
    area: 'Movimientos',
    titulo: 'Ponle categoría a cada gasto',
    texto:
      'Cada gasto o ingreso tiene una categoría (Comida, Transporte…). Toca los chips o desliza para asignarla. La app aprende y la próxima vez lo hace sola.',
    detalle:
      'Si pasas plata de una cuenta tuya a otra (de tu banco a Nequi), es un traslado: no es un gasto ni un ingreso porque la plata sigue siendo tuya, y no cuenta en tus informes.',
    ruta: '/movimientos',
    accion: 'Ver movimientos',
  },
  {
    id: 'presupuesto',
    area: 'Presupuesto',
    titulo: 'Cuánto puedes gastar',
    texto:
      'Ponle un límite al mes a cada categoría. Una barra te muestra cuánto llevas y te avisamos antes de pasarte.',
    ruta: '/presupuesto',
    accion: 'Hacer mi presupuesto',
  },
  {
    id: 'metas',
    area: 'Metas y deudas',
    titulo: 'Ahorra para algo, paga lo que debes',
    texto:
      'En Metas guardas para un viaje o un fondo de emergencia y ves cuánto falta. En Deudas ves lo que debes y cuánto ahorras pagando primero la más cara.',
    ruta: '/metas',
    accion: 'Crear una meta',
  },
  {
    id: 'informes',
    area: 'Informes',
    titulo: 'En qué se va tu plata',
    texto:
      'Un informe claro por categoría y por comercio. Sirve para entender tus hábitos y decidir qué recortar sin sufrir.',
    ruta: '/informe',
    accion: 'Ver mi informe',
  },
  {
    id: 'asistente',
    area: 'Asistente de IA',
    titulo: 'Pregúntale a tu plata',
    texto:
      'Escribe como hablas: «¿cuánto gasté en domicilios este mes?». El asistente mira tus movimientos y te responde. Solo lee tus datos si tú lo autorizas.',
    ruta: '/asistente',
    accion: 'Probar el asistente',
  },
  {
    id: 'privacidad',
    area: 'Privacidad',
    titulo: 'Tus datos son tuyos',
    texto:
      'Con el correo solo leemos los avisos de bancos y billeteras. No leemos tus correos personales, no enviamos ni borramos nada y puedes quitar el permiso cuando quieras. También puedes descargar o borrar tus datos.',
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

/** ¿Debe abrirse solo? Solo si está pendiente (cuenta nueva) y la persona no lo cerró antes. */
export const debeAbrirseSolo = (e) => !!e?.pendiente && !e.terminado && !e.saltado

/** ¿Hay un recorrido a medias que se pueda retomar? */
export const sePuedeRetomar = (e) => !!e?.empezado && !e.terminado && !e.saltado && !e.pendiente
