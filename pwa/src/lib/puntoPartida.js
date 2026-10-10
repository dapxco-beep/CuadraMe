// Punto de partida («empezar desde hoy» / «recrear mi histórico»): reglas puras y textos.
// El servidor es quien filtra (correos, extractos, archivos, informes, consejos); esto solo ayuda a
// elegir, decir las cosas en lenguaje llano y recordar «decidir después».

export const MODOS = {
  hoy: {
    id: 'hoy',
    titulo: 'Empezar desde hoy',
    recomendado: true,
    explicacion:
      'Tomamos el saldo de hoy de cada cuenta como punto de partida y solo registramos lo que pase desde ahora. Lo anterior no estorba ni aparece por revisar.',
    ejemplo: 'Ejemplo: hoy tienes $1.200.000 en tu cuenta de ahorros; ese es tu saldo inicial.',
  },
  historico: {
    id: 'historico',
    titulo: 'Recrear mi histórico',
    recomendado: false,
    explicacion:
      'Eliges desde cuándo (3, 6, 12 meses o una fecha) y traemos tus extractos de ese tiempo para ver tu historia completa mes a mes.',
    ejemplo: 'Ejemplo: desde enero, con el extracto de cada mes de cada cuenta.',
  },
}

export const AYUDA_ELEGIR =
  '¿Cuál elijo? Si solo quieres controlar desde ahora, elige «Empezar desde hoy». Si quieres ver tu historia, elige «Recrear mi histórico».'

export const OPCIONES_MESES = [3, 6, 12]

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

/** '2026-10-09' -> '9 de octubre de 2026' (sin pasar por zonas horarias). */
export function fechaLarga(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''))
  if (!m) return ''
  return `${Number(m[3])} de ${MESES[Number(m[2]) - 1]} de ${m[1]}`
}

const dos = (n) => String(n).padStart(2, '0')

/** Primer día del mes de hace `meses` meses (igual que el servidor). `hoy` solo para pruebas. */
export function fechaDesdeMeses(meses, hoy = new Date()) {
  let a = hoy.getFullYear()
  let m = hoy.getMonth() + 1 - meses
  while (m <= 0) {
    a -= 1
    m += 12
  }
  return `${a}-${dos(m)}-01`
}

export function hoyISO(hoy = new Date()) {
  return `${hoy.getFullYear()}-${dos(hoy.getMonth() + 1)}-${dos(hoy.getDate())}`
}

/** '1.200.000', '$ 1.200.000,50', '1200000.5', '-350.000' -> número; '' o ilegible -> null. */
export function parsearMonto(texto) {
  let t = String(texto ?? '').replace(/[^\d.,-]/g, '')
  if (!t || t === '-') return null
  const negativo = t.startsWith('-')
  t = t.replace(/-/g, '')
  const coma = t.lastIndexOf(',')
  const punto = t.lastIndexOf('.')
  if (coma > -1 && punto > -1) {
    // el último separador es el decimal
    t = coma > punto ? t.replace(/\./g, '').replace(',', '.') : t.replace(/,/g, '')
  } else if (coma > -1) {
    t = t.split(',').length > 2 || t.length - coma - 1 === 3 ? t.replace(/,/g, '') : t.replace(',', '.')
  } else if (punto > -1) {
    t = t.split('.').length > 2 || t.length - punto - 1 === 3 ? t.replace(/\./g, '') : t
  }
  const n = Number(t)
  if (!Number.isFinite(n)) return null
  return negativo ? -n : n
}

/** Una línea que dice qué se eligió: «Desde el 9 de octubre de 2026 · Empezar desde hoy». */
export function descripcionPunto(pp) {
  if (!pp?.definido) return 'Aún no elegiste desde cuándo.'
  return `Desde el ${fechaLarga(pp.fecha)} · ${MODOS[pp.modo]?.titulo || ''}`
}

/** «Te faltan extractos de: abril, mayo» por cuenta (solo las cuentas a las que les falta algo). */
export function avisosFaltantes(cobertura) {
  return (cobertura?.cuentas || [])
    .filter((c) => (c.faltan || []).length > 0)
    .map((c) => ({ cuentaId: c.cuenta_id, nombre: c.nombre, texto: `Te faltan extractos de: ${c.faltan_texto}` }))
}

// ── «Decidir después»: no insistir cada vez que abre la pantalla ──────────
const CLAVE_POSPUESTO = 'cuadrame:punto-partida-pospuesto'
const DIAS_POSPUESTO = 7

export function puntoDePartidaPospuesto(ahora = Date.now()) {
  try {
    const t = Number(localStorage.getItem(CLAVE_POSPUESTO))
    return Boolean(t) && ahora - t < DIAS_POSPUESTO * 86400000
  } catch {
    return false
  }
}

export function posponerPuntoDePartida(ahora = Date.now()) {
  try {
    localStorage.setItem(CLAVE_POSPUESTO, String(ahora))
  } catch {
    /* sin almacenamiento: simplemente vuelve a preguntar */
  }
}
