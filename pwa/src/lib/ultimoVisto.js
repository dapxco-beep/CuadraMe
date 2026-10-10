// Último visto: copia de lo que la app leyó por última vez (ver explicación abajo). Vive aparte de
// api.js para que las pantallas lo lean sin depender del cliente de red.
const copiar = (v) => (v !== null && typeof v === 'object' ? JSON.parse(JSON.stringify(v)) : v)

// ── Último visto (stale-while-revalidate + lectura sin red) ──────────────────────────────
// Cada lectura exitosa deja una copia de "lo último que se vio". Sirve para dos cosas:
//  1. Pintar una pantalla AL INSTANTE con lo que se vio hace poco (leerVisto) mientras llega lo
//     nuevo, en vez de mostrar un esqueleto (la pantalla se actualiza sola al llegar el dato).
//  2. Sin conexión (fetch falla): la lectura devuelve lo último visto en vez de un error, y la app
//     avisa con el evento "cuadrame:datos-guardados" para mostrar «Sin conexión».
// Privacidad: la copia en memoria vive solo mientras la app está abierta. En el celular (localStorage)
// solo se guardan unas pocas lecturas (cuentas, movimientos recientes, resumen, presupuesto…): nunca
// claves, correos, conexiones ni datos de terceros. Se borra al cerrar sesión (olvidarVistos) y está
// separada por usuario ("cuadrame:visto:<usuario>").
const VISTO_FRESCO_MS = 30 * 60 * 1000 // para pintar al instante
const VISTO_SIN_RED_MS = 7 * 24 * 3600 * 1000 // para leer sin conexión
const VISTO_MAX_MEMORIA = 80
const VISTO_MAX_BYTES = 180 * 1024
const CLAVE_VISTO = 'cuadrame:visto:'
const CLAVE_VISTO_UID = 'cuadrame:visto-uid'
const PERSISTIBLE =
  /^\/(cuentas(\/resumen)?|categorias(\?incluir_inactivas=true)?|reportes\/(mensual|tendencias)(\?[\w=&.-]+)?|presupuestos(\/disponible-hoy|\/en-mi-bolsillo)?|reportes\/flujo-caja-futuro\?meses=\d+|planificacion\/proyeccion|movimientos\?limit=\d+&offset=0(&desde=[\d-]+)?|patrimonio|metas|deudas|recurrentes|sincronizacion\/estado)$/
let vistosActivos = import.meta.env.MODE !== 'test'
const vistos = new Map() // "uid|ruta" -> { valor, en }
let uidVisto = null
let temporizadorVistos = null
let avisoSinRed = false

function almacen() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

function hidratarVistos(uid) {
  const ls = almacen()
  if (!ls || !uid) return
  try {
    const crudo = ls.getItem(CLAVE_VISTO + uid)
    if (!crudo) return
    for (const [ruta, [en, valor]] of Object.entries(JSON.parse(crudo))) {
      if (!vistos.has(uid + '|' + ruta)) vistos.set(uid + '|' + ruta, { valor, en })
    }
  } catch {
    /* copia dañada: se ignora */
  }
}

function fijarUsuarioVisto(uid) {
  if (!uid || uid === 'anon' || uid === uidVisto) return
  uidVisto = uid
  try {
    almacen()?.setItem(CLAVE_VISTO_UID, uid)
  } catch {
    /* sin almacenamiento */
  }
  hidratarVistos(uid)
}

if (vistosActivos) {
  try {
    const uid = almacen()?.getItem(CLAVE_VISTO_UID)
    if (uid) {
      uidVisto = uid
      hidratarVistos(uid)
    }
  } catch {
    /* sin almacenamiento */
  }
}

function persistirVistos() {
  temporizadorVistos = null
  const ls = almacen()
  if (!ls || !uidVisto) return
  try {
    const prefijo = uidVisto + '|'
    const filas = [...vistos.entries()]
      .filter(([k]) => k.startsWith(prefijo) && PERSISTIBLE.test(k.slice(prefijo.length)))
      .sort((a, b) => b[1].en - a[1].en)
    const salida = {}
    let bytes = 0
    for (const [k, v] of filas) {
      const texto = JSON.stringify(v.valor)
      if (bytes + texto.length > VISTO_MAX_BYTES) continue
      bytes += texto.length
      salida[k.slice(prefijo.length)] = [v.en, v.valor]
    }
    ls.setItem(CLAVE_VISTO + uidVisto, JSON.stringify(salida))
  } catch {
    /* cuota llena o modo privado: la app sigue igual, solo sin copia en el celular */
  }
}

export function recordarVisto(uid, ruta, valor) {
  if (!vistosActivos || uid === 'anon') return
  fijarUsuarioVisto(uid)
  const k = uid + '|' + ruta
  vistos.delete(k) // reinsertar al final: el Map queda ordenado por uso
  vistos.set(k, { valor, en: Date.now() })
  while (vistos.size > VISTO_MAX_MEMORIA) vistos.delete(vistos.keys().next().value)
  if (PERSISTIBLE.test(ruta) && !temporizadorVistos && typeof setTimeout === 'function') {
    temporizadorVistos = setTimeout(persistirVistos, 2000)
  }
}

/** Lo último visto de una ruta (copia) o undefined. Síncrono: sirve para el primer pintado. */
export function leerVisto(ruta, maxEdadMs = VISTO_FRESCO_MS) {
  if (!vistosActivos || !uidVisto) return undefined
  const v = vistos.get(uidVisto + '|' + ruta)
  if (!v || Date.now() - v.en > maxEdadMs) return undefined
  return copiar(v.valor)
}

/** Borra lo último visto (memoria y celular). Se llama al cerrar sesión. */
export function olvidarVistos() {
  vistos.clear()
  uidVisto = null
  if (temporizadorVistos) {
    clearTimeout(temporizadorVistos)
    temporizadorVistos = null
  }
  const ls = almacen()
  if (!ls) return
  try {
    const borrar = []
    for (let i = 0; i < ls.length; i++) {
      const k = ls.key(i)
      if (k && (k.startsWith(CLAVE_VISTO) || k === CLAVE_VISTO_UID)) borrar.push(k)
    }
    borrar.forEach((k) => ls.removeItem(k))
  } catch {
    /* nada que borrar */
  }
}

export function avisarDatosGuardados() {
  if (avisoSinRed || typeof window === 'undefined') return
  avisoSinRed = true
  window.dispatchEvent(new CustomEvent('cuadrame:datos-guardados'))
}
export function avisarConexionOk() {
  if (!avisoSinRed || typeof window === 'undefined') return
  avisoSinRed = false
  window.dispatchEvent(new CustomEvent('cuadrame:conexion-ok'))
}

/** Activa o desactiva el recuerdo (las pruebas lo desactivan por defecto). */
export function activarVistos(activo) {
  vistosActivos = !!activo
  if (!activo) olvidarVistos()
}

/** Lo último visto de una ruta para leer SIN conexión (hasta 7 días), o undefined. */
export function vistoSinRed(uid, ruta) {
  if (!vistosActivos) return undefined
  const v = vistos.get(uid + '|' + ruta)
  if (!v || Date.now() - v.en > VISTO_SIN_RED_MS) return undefined
  return copiar(v.valor)
}

// Lo último visto de las lecturas que las pantallas principales usan para pintar al instante.
// Las rutas deben coincidir con las de arriba (misma cadena = misma copia).
export const visto = {
  cuentas: () => leerVisto('/cuentas'),
  resumenCuentas: () => leerVisto('/cuentas/resumen'),
  movimientos: (limit = 100) => leerVisto(`/movimientos?limit=${limit}&offset=0`),
  movimientosDesde: (limit, desde) => leerVisto(`/movimientos?limit=${limit}&offset=0&desde=${desde}`),
  reporteMensual: () => leerVisto('/reportes/mensual'),
  disponibleHoy: () => leerVisto('/presupuestos/disponible-hoy'),
  enMiBolsillo: () => leerVisto('/presupuestos/en-mi-bolsillo'),
  tendencias: (meses = 6) => leerVisto(`/reportes/tendencias?meses=${meses}`),
  sincronizacionEstado: () => leerVisto('/sincronizacion/estado'),
  presupuestos: () => leerVisto('/presupuestos'),
  flujoCajaFuturo: (meses = 3) => leerVisto(`/reportes/flujo-caja-futuro?meses=${meses}`),
  proyeccionPresupuestos: () => leerVisto('/planificacion/proyeccion'),
}
