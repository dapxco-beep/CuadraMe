// Los dos usos del correo, dichos en palabras. Sin React, fáciles de probar.
//   movimientos = notificaciones del banco: así ves en el momento lo que gastas (día a día). Se aprueban en la
//                 pantalla Movimientos («Por revisar · N del correo»).
//   extractos   = el extracto mensual del banco: sirve para confirmar y cuadrar el mes (conciliar). Los del correo
//                 y los que subes como archivo viven juntos en la sección «Extractos».

export const CARRILES = ['movimientos', 'extractos']

export const NOMBRE_CARRIL = {
  movimientos: 'Movimientos',
  extractos: 'Extractos',
}

export const TEXTO_CARRIL = {
  movimientos: 'Las notificaciones de tu banco: así ves en el momento lo que gastas.',
  extractos: 'El extracto mensual del banco: sirve para confirmar y cuadrar el mes.',
}

// Ejemplo de una línea para «¿cuál es la diferencia?».
export const EJEMPLO_CARRIL = {
  movimientos: 'Ejemplo: «Compra por $45.000 en Éxito» te llega al celular y aquí lo apruebas el mismo día.',
  extractos: 'Ejemplo: el PDF de septiembre sirve para confirmar que no falta ni sobra nada del mes.',
}

export const BOTON_CARRIL = {
  movimientos: 'Traer movimientos del correo',
  extractos: 'Buscar extractos',
}

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`

// Tarea (de GET /sincronizacion/estado) -> carril al que pertenece (o null).
export function carrilDeTarea(t) {
  if (t?.carril) return t.carril
  if (t?.id === 'correos_por_revisar') return 'movimientos'
  if (['extractos_por_conciliar', 'falta_clave', 'extractos_sin_leer', 'cuadre_no_cuadra'].includes(t?.id)) return 'extractos'
  return null
}

/** «3 movimientos por revisar · 1 extracto por conciliar» (no mezcla los dos conteos). '' si no hay ninguno. */
export function resumenCarriles(tareas) {
  const lista = tareas || []
  const suma = (ids) => lista.filter((t) => ids.includes(t.id)).reduce((s, t) => s + (t.cantidad || 0), 0)
  const mov = suma(['correos_por_revisar'])
  const ext = suma(['extractos_por_conciliar', 'falta_clave'])
  const partes = []
  if (mov) partes.push(`${plural(mov, 'movimiento', 'movimientos')} por revisar`)
  if (ext) partes.push(`${plural(ext, 'extracto', 'extractos')} por revisar`)
  return partes.join(' · ')
}

/** Línea de contadores de la tarjeta de un carril, a partir de GET .../estado `carriles[carril]`. */
export function contadoresCarril(carril, c) {
  if (!c) return []
  if (carril === 'movimientos') {
    return [
      { clave: 'por_revisar', texto: plural(c.por_revisar || 0, 'por revisar', 'por revisar') },
      { clave: 'ya_registrados', texto: plural(c.ya_registrados || 0, 'ya registrado', 'ya registrados') },
      ...(c.provisionales ? [{ clave: 'provisionales', texto: `${plural(c.provisionales, 'falta', 'faltan')} confirmar con el extracto` }] : []),
    ]
  }
  return [
    { clave: 'encontrados', texto: plural(c.encontrados || 0, 'encontrado', 'encontrados') },
    { clave: 'por_conciliar', texto: plural(c.por_conciliar || 0, 'por revisar', 'por revisar') },
    ...(c.con_clave_pendiente ? [{ clave: 'clave', texto: `${plural(c.con_clave_pendiente, 'necesita', 'necesitan')} clave` }] : []),
    { clave: 'al_dia', texto: `${c.al_dia || 0} al día` },
  ]
}

/** Texto de lo que pasó en la última lectura de un carril (respuesta de POST /correos/sincronizar). */
export function resumenLectura(carril, r) {
  if (!r) return ''
  if (r.aviso) return r.aviso
  if (carril === 'movimientos') {
    const n = r.nuevos || 0
    return n ? `Encontré ${plural(n, 'movimiento nuevo', 'movimientos nuevos')}.` : 'No hay movimientos nuevos en tu correo.'
  }
  const e = r.extractos_encontrados ?? r.extractos_nuevos ?? 0
  return e ? `Encontré ${plural(e, 'extracto', 'extractos')}.` : 'No hay extractos nuevos en tu correo.'
}

/**
 * «Por hacer» separado por carril y con el nombre de cada uno. Los grupos salen en el orden en que
 * aparece su primera tarea; lo que no es del correo va en «Otras cosas» (sin título si es lo único).
 */
export function gruposDeTareas(tareas) {
  const grupos = []
  for (const t of tareas || []) {
    const clave = carrilDeTarea(t) || 'general'
    let g = grupos.find((x) => x.clave === clave)
    if (!g) {
      g = { clave, nombre: clave === 'general' ? '' : NOMBRE_CARRIL[clave], tareas: [] }
      grupos.push(g)
    }
    g.tareas.push(t)
  }
  if (grupos.length > 1) {
    const general = grupos.find((g) => g.clave === 'general')
    if (general) general.nombre = 'Otras cosas'
  }
  return grupos
}

const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const fechaCorta = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? `${Number(m[3])} ${MESES_CORTOS[Number(m[2]) - 1]}` : ''
}

export const SIN_CORREOS_NUEVOS = 'No vimos correos nuevos de tus bancos. Revisa que sigan llegando a este Gmail o busca uno por asunto.'

/**
 * Resumen de la última lectura de movimientos (carriles.movimientos.ultima_lectura de la API):
 * «12 correos desde el 15 oct → 2 nuevos, 9 ya registrados, 1 aviso descartado». Solo cifras: la API no
 * manda contenido de correos. Si leyó 0 dos veces seguidas avisa claro. null si aún no hay lectura.
 */
export function textoUltimaLectura(u) {
  if (!u || typeof u.leidos !== 'number') return null
  if (u.leidos === 0) {
    return (u.ceros_seguidos || 0) >= 2
      ? SIN_CORREOS_NUEVOS
      : `Última lectura de movimientos: Gmail no devolvió correos${u.desde ? ` desde el ${fechaCorta(u.desde)}` : ''}.`
  }
  const partes = []
  if (u.nuevos) partes.push(plural(u.nuevos, 'nuevo', 'nuevos'))
  if (u.ya_registrados) partes.push(`${u.ya_registrados} ya registrado${u.ya_registrados === 1 ? '' : 's'}`)
  if (u.ignorados) partes.push(plural(u.ignorados, 'ignorado', 'ignorados') + (u.motivo_frecuente && !u.avisos_descartados ? ` (${u.motivo_frecuente})` : ''))
  if (u.avisos_descartados) partes.push(plural(u.avisos_descartados, 'aviso descartado', 'avisos descartados'))
  const desde = u.desde ? ` desde el ${fechaCorta(u.desde)}` : ''
  return `Última lectura de movimientos: ${plural(u.leidos, 'correo', 'correos')}${desde} → ${partes.join(', ') || 'nada nuevo'}`
}
