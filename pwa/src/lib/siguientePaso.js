// «Traer movimientos» como asistente: de todo lo que está pendiente se escoge UNA cosa a la vez.
// Puro (sin React) y probado en test/siguiente_paso.test.js. Orden de prioridad:
//   conectar (solo en el primer uso) → clave faltante → crear cuenta de tarjeta/banco → extracto en otra cuenta →
//   extractos a medias → importar faltantes (conciliar) → correos por revisar → lo demás → categorizar repetidos y
//   correos descartados (opcionales) → cuadre.
// «Todo al día» es una promesa: solo se dice si NO queda nada, ni siquiera opcional (ver estadoGeneral).
// Cada paso trae el texto (sin jerga) y el nombre del botón; qué hace el botón lo decide la pantalla por `id`.

export const ORDEN_PASOS = [
  'conectar', 'punto_partida', 'falta_clave', 'sin_cuenta', 'extracto_cuenta_dudosa', 'a_medias', 'extractos_por_conciliar',
  'correos_por_revisar', 'movimientos_por_confirmar', 'extractos_sin_leer', 'posibles_duplicados', 'cuadre_no_cuadra',
  'movimientos_por_categorizar', 'correos_descartados',
]
const FIJOS = ['conectar', 'punto_partida', 'falta_clave', 'sin_cuenta', 'extracto_cuenta_dudosa', 'a_medias']

const n = (x) => Number(x) || 0
const plural = (c, uno, varios) => `${c} ${c === 1 ? uno : varios}`

/** «agosto» a partir de «Agosto 2026» o «agosto de 2026»; vacío si no hay mes. */
const soloMes = (mes) => String(mes || '').split(/\s|-/)[0].toLowerCase()

function textoDe(id, { cantidad = 0, claveConfigurada = false, banco = '', aMedias = [], tarea = null }) {
  switch (id) {
    case 'conectar':
      return { titulo: 'Conecta tu Gmail', detalle: 'Así traigo solos tus movimientos y extractos. Solo pido permiso de lectura.', boton: 'Conectar Gmail' }
    case 'punto_partida':
      return { titulo: '¿Desde cuándo leo tu correo?', detalle: 'Elige tu fecha de inicio para no traer movimientos viejos.', boton: 'Elegir la fecha' }
    case 'falta_clave':
      return claveConfigurada
        ? { titulo: 'La clave de tu PDF no abrió tus extractos', detalle: 'Revísala y vuelvo a probar de una vez.', boton: 'Cambiar la clave' }
        : { titulo: 'Falta la clave de tu PDF', detalle: 'Tus extractos vienen con clave. Ponla una vez y los abro solos.', boton: 'Ponerla ahora' }
    case 'sin_cuenta':
      return {
        titulo: banco ? `Crea tu cuenta de ${banco}` : 'Crea la cuenta de tu banco',
        detalle: 'Llegó un extracto y aún no tienes esa cuenta. Se crea en un momento.',
        boton: 'Crear la cuenta',
      }
    case 'a_medias': {
      const p = aMedias[0] || {}
      const mes = soloMes(p.mes)
      return aMedias.length === 1
        ? {
            titulo: `Sigue con tu extracto${mes ? ` de ${mes}` : ''}`,
            detalle: `${p.cuenta || 'Tu cuenta'}: faltan importar ${plural(n(p.faltan), 'movimiento', 'movimientos')}.`,
            boton: 'Seguir',
          }
        : { titulo: `Sigue con tus ${aMedias.length} extractos a medias`, detalle: `Empiezo por ${p.cuenta || 'el primero'}${mes ? ` de ${mes}` : ''}.`, boton: 'Seguir' }
    }
    case 'extractos_por_conciliar':
      return {
        titulo: cantidad === 1 ? 'Revisa tu extracto' : `Revisa tus ${cantidad} extractos`,
        detalle: 'Miro qué trae y tú confirmas lo que falta registrar.',
        boton: 'Revisar',
      }
    case 'correos_por_revisar':
      return {
        titulo: cantidad === 1 ? 'Revisa 1 movimiento' : `Revisa ${cantidad} movimientos`,
        detalle: 'Los leí de tus correos. Mira la fecha y el monto, y apruébalos.',
        boton: 'Revisar',
      }
    case 'movimientos_por_confirmar':
      return { titulo: 'Confirma si son tuyos', detalle: `${plural(cantidad, 'movimiento', 'movimientos')} del extracto por confirmar.`, boton: 'Confirmar' }
    case 'extractos_sin_leer':
      return {
        titulo: cantidad === 1 ? 'Hay extractos que no se pudieron leer' : `Hay ${cantidad} grupos de extractos que no se pudieron leer`,
        detalle: 'Te digo de dónde vino cada uno y qué hacer: reintentar, subirlo de nuevo o quitarlo.',
        boton: 'Ver cuáles',
      }
    case 'extracto_cuenta_dudosa':
      return {
        titulo: cantidad === 1 ? 'Un extracto está en otra cuenta' : `${cantidad} extractos están en otra cuenta`,
        detalle: 'Parece de tu tarjeta de crédito y quedó en una cuenta de ahorros. Pásalo a la cuenta correcta.',
        boton: 'Ver y pasarlo',
      }
    case 'correos_descartados':
      return {
        titulo: cantidad === 1 ? 'Hay 1 correo descartado' : `Hay ${cantidad} correos descartados`,
        detalle: 'Los descartaste al borrar un movimiento parecido. Mira si alguno sí era tuyo.',
        boton: 'Verlos',
      }
    case 'posibles_duplicados':
      return { titulo: 'Puede haber movimientos repetidos', detalle: 'Mira cuáles se parecen y deja solo uno.', boton: 'Ver los repetidos' }
    case 'movimientos_por_categorizar':
      return {
        titulo: cantidad === 1 ? 'Pon categoría a 1 comercio' : `Pon categoría a ${cantidad} comercios`,
        detalle: 'Lo hago una vez y lo recuerdo para los próximos.',
        boton: 'Poner categorías',
      }
    case 'cuadre_no_cuadra':
      return { titulo: 'Un mes no cuadra con tu extracto', detalle: 'Escribe el saldo que dice el extracto y miro dónde está la diferencia.', boton: 'Cuadrar' }
    default:
      return { titulo: tarea?.titulo || 'Hay algo por revisar', detalle: tarea?.detalle || '', boton: 'Resolver' }
  }
}

/**
 * Lista ordenada de lo pendiente. `tareas` = GET /sincronizacion/estado → tareas; `aMedias` = extractosAMedias(estado).
 * `primerUso` = sin Gmail y sin nada que mostrar todavía: ahí lo primero es conectar.
 * Cada paso: { id, titulo, detalle, boton, cantidad, opcional, tarea }.
 */
export function construirPasos({ tareas = [], aMedias = [], conectado = true, primerUso = false, claveConfigurada = false, sinCuenta = [], puntoPendiente = false } = {}) {
  const por = new Map()
  for (const t of tareas || []) por.set(t.id, t)
  const pasos = []
  const poner = (id, cantidad, tarea = null, opcional = false, extra = {}) => {
    pasos.push({ id, cantidad, tarea, opcional, ...textoDe(id, { cantidad, claveConfigurada, aMedias, tarea, ...extra }) })
  }
  if (!conectado && primerUso) poner('conectar', 1)
  // La fecha de inicio es lo primero en el primer uso; después queda como una invitación suave al final.
  if (puntoPendiente) poner('punto_partida', 1, null, !primerUso)
  if (por.has('falta_clave')) poner('falta_clave', n(por.get('falta_clave').cantidad), por.get('falta_clave'))
  if (por.has('sin_cuenta')) poner('sin_cuenta', n(por.get('sin_cuenta').cantidad), por.get('sin_cuenta'), false, { banco: sinCuenta.length === 1 ? sinCuenta[0].banco : '' })
  if (por.has('extracto_cuenta_dudosa')) poner('extracto_cuenta_dudosa', n(por.get('extracto_cuenta_dudosa').cantidad), por.get('extracto_cuenta_dudosa'))
  if (aMedias.length) poner('a_medias', aMedias.length)
  for (const id of ORDEN_PASOS) {
    if (FIJOS.includes(id)) continue
    const t = por.get(id)
    if (t) poner(id, n(t.cantidad), t, Boolean(t.opcional))
  }
  // Tareas nuevas del servidor que esta lista aún no conoce: al final, con su propio texto.
  for (const t of tareas || []) if (!ORDEN_PASOS.includes(t.id)) poner(t.id, n(t.cantidad), t, Boolean(t.opcional))
  // Lo opcional (categorizar) siempre queda después de lo obligatorio (sort estable).
  return pasos.sort((a, b) => Number(a.opcional) - Number(b.opcional))
}

/** Lo que de verdad hay que hacer (sin lo opcional). */
export const obligatorios = (pasos) => (pasos || []).filter((p) => !p.opcional)

// Cómo se nombra cada pendiente OPCIONAL cuando es lo único que queda («Casi todo al día · solo queda…»).
function nombrePendienteOpcional(p) {
  const c = p.cantidad || 0
  switch (p.id) {
    case 'correos_descartados':
      return c === 1 ? '1 correo descartado por mirar' : `${c} correos descartados por mirar`
    case 'movimientos_por_categorizar':
      return c === 1 ? '1 comercio sin categoría' : `${c} comercios sin categoría`
    case 'punto_partida':
      return 'elegir desde cuándo leo tu correo'
    default:
      return (p.titulo || 'algo opcional').replace(/^./, (ch) => ch.toLowerCase())
  }
}

/**
 * { alDia, casi, titulo, pendiente } del estado grande de arriba.
 *  · «Todo al día» solo si NO queda nada (ni obligatorio ni opcional).
 *  · «Casi todo al día» si solo quedan cosas opcionales: se nombran en `pendiente`.
 *  · si no, «Tienes N cosas por hacer».
 */
export function estadoGeneral(pasos) {
  const k = obligatorios(pasos).length
  if (k > 0) return { alDia: false, titulo: k === 1 ? 'Tienes 1 cosa por hacer' : `Tienes ${k} cosas por hacer` }
  const opcionales = (pasos || []).filter((p) => p.opcional)
  if (opcionales.length === 0) return { alDia: true, titulo: 'Todo al día' }
  return { alDia: false, casi: true, titulo: 'Casi todo al día', pendiente: opcionales.map(nombrePendienteOpcional).join(' y ') }
}

/**
 * «Paso 1 de 3»: `maximo` es la mayor cantidad de pasos que se vio en esta visita; así, al resolver uno,
 * el contador avanza («Paso 2 de 3») en vez de achicarse. Devuelve null si no hay nada pendiente.
 */
export function progresoPasos(restantes, maximo) {
  if (!restantes) return null
  const de = Math.max(restantes, maximo || 0)
  return { n: de - restantes + 1, de, pct: Math.round(((de - restantes) / de) * 100) }
}

/** Frase del avance en línea mientras se busca: «Leyendo tus extractos… 3 de 6». */
export function textoBusqueda({ fase, leidos = 0, total = 0 } = {}) {
  const cuenta = total ? ` ${leidos} de ${total}` : ''
  if (fase === 'extractos') return `Leyendo tus extractos…${cuenta}`
  if (fase === 'movimientos') return `Leyendo tus avisos del banco…${cuenta}`
  if (fase === 'clave') return 'Probando tu clave en los PDF…'
  if (fase === 'saldos') return 'Releyendo saldos…'
  return `Leyendo tu correo…${cuenta}`
}
