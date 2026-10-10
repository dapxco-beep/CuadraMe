// Lógica pura del asistente «Registro automático al pagar con el iPhone». Sin React.
//
// Decisiones clave:
//  - El paso donde quedó la persona se guarda en localStorage (con try/catch: en modo privado
//    simplemente empieza de cero). Solo se guarda un número, nunca la clave.
//  - «Probar ahora» usa la SESIÓN (/movimientos/rapido-prueba), no la clave: así NO toca el
//    «último uso de la clave», y ese dato queda reservado para saber si el atajo REAL ya envió algo.
//  - Los errores se traducen a: qué pasó en llano + el siguiente paso concreto.

export const CLAVE_PASO = 'cuadrame:atajo-paso'
export const PASOS_TOTAL = 3

export function leerPaso() {
  try {
    const crudo = localStorage.getItem(CLAVE_PASO)
    if (crudo === null) return -1
    const n = Number(crudo)
    return Number.isInteger(n) && n >= -1 && n <= PASOS_TOTAL ? n : -1
  } catch {
    return -1
  }
}

export function guardarPaso(n) {
  try {
    localStorage.setItem(CLAVE_PASO, String(n))
  } catch {
    /* sin almacenamiento: la persona empieza del principio la próxima vez */
  }
}

/**
 * Traduce un fallo de la prueba a algo que entiende una persona no técnica.
 * Devuelve { titulo, texto, accion?: { texto, a } } — `a` es una ruta de la app.
 */
export function explicarErrorPrueba(err) {
  const status = err?.status
  if (status === 404) {
    return {
      titulo: 'Aún no tienes dónde anotar el pago',
      texto: 'CuadraMe necesita al menos una cuenta (por ejemplo Nu, Nequi o tu banco) para anotar tus pagos. Crea una y vuelve a probar.',
      accion: { texto: 'Crear una cuenta', a: '/cuentas' },
    }
  }
  if (status === 401) {
    return {
      titulo: 'Tu sesión se cerró',
      texto: 'Vuelve a entrar a CuadraMe y toca «Probar ahora» otra vez.',
    }
  }
  if (status === 429) {
    return {
      titulo: 'Hiciste varias pruebas seguidas',
      texto: 'Espera un par de minutos y vuelve a intentar.',
    }
  }
  if (err?.codigo === 'no-llego') {
    return {
      titulo: 'La prueba salió, pero no la vemos',
      texto: 'Toca «Probar ahora» otra vez. Si se repite, cierra y abre CuadraMe.',
    }
  }
  if (!status) {
    return {
      titulo: 'Sin conexión por ahora',
      texto: 'Parece que no hay internet. Revisa tu conexión y vuelve a probar.',
    }
  }
  return {
    titulo: 'No pudimos hacer la prueba',
    texto: err?.message || 'Intenta de nuevo en un momento.',
  }
}

/** Qué revisar cuando la prueba del servidor sale bien pero el iPhone aún no envía nada. */
export const SI_NO_LLEGA = [
  { id: 'clave', texto: 'La clave quedó mal pegada: vuelve al paso 1, crea una clave nueva y pégala al instalar el atajo.' },
  { id: 'atajo', texto: 'El atajo no está instalado: repite el paso 2 y toca «Agregar atajo».' },
  { id: 'auto', texto: 'La automatización pregunta antes de correr: en el paso 3 marca «Ejecutar inmediatamente».' },
]

export function fechaLegible(iso) {
  if (!iso) return ''
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('es-CO', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
}
