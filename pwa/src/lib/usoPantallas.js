import { api } from './api'

// Medición anónima de uso: avisa QUÉ pantalla se abrió (solo su nombre, p. ej. «/presupuesto?tab=fijos»), una vez por sesión.
// El servidor solo la cuenta si la persona aceptó «estadísticas anónimas»; si no, no hace nada. Nunca estorba a la app.

const ID = /^([0-9a-f]{8}-[0-9a-f]{4}-|\d{3,}$|[0-9a-f]{16,}$)/i

/** «/movimientos/3f2a…» -> «/movimientos/:id»; conserva solo `?tab=` (sin ningún otro dato de la dirección). */
export function rutaAnonima(pathname = '', search = '') {
  const partes = String(pathname || '/')
    .toLowerCase()
    .split('/')
    .map((p) => (p && ID.test(p) ? ':id' : p))
  const base = partes.join('/').replace(/\/+$/, '') || '/'
  const tab = new URLSearchParams(search).get('tab')
  return tab && /^[a-z_]{1,24}$/.test(tab.toLowerCase()) ? `${base}?tab=${tab.toLowerCase()}` : base
}

const vistas = new Set()

export function anotarPantalla(pathname, search, cliente = api) {
  const ruta = rutaAnonima(pathname, search)
  if (vistas.has(ruta) || ruta.length > 90) return false
  vistas.add(ruta)
  try {
    Promise.resolve(cliente.usoPantalla?.(ruta)).catch(() => {})
  } catch {
    /* nunca debe afectar a la app */
  }
  return true
}

export function reiniciarVistas() {
  vistas.clear()
}
