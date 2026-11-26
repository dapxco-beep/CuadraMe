// Ayudas para instalar CuadraMe en iPhone. Safari NO deja instalar con un solo toque (no existe el botón «Instalar»
// de Android): lo más cercano es abrir de una vez el menú de compartir, donde está «Añadir a pantalla de inicio».

/** ¿Es un navegador integrado de otra app (Instagram, Facebook, WhatsApp…)? Ahí no se puede instalar: hay que abrir Safari. */
export function esNavegadorIntegrado(ua = typeof navigator !== 'undefined' ? navigator.userAgent : '') {
  if (!/iPhone|iPad|iPod/i.test(ua)) return false
  if (/FBAN|FBAV|Instagram|Line\/|MicroMessenger|Snapchat|TikTok|musical_ly|WhatsApp|GSA\//i.test(ua)) return true
  // Safari y Chrome de iPhone incluyen «Safari/» en su identificación; una vista web embebida no.
  return !/Safari\//i.test(ua)
}

export const puedeCompartir = () => typeof navigator !== 'undefined' && typeof navigator.share === 'function'

/** Abre el menú de compartir del iPhone con el enlace de CuadraMe. Devuelve 'abierto' | 'cancelado' | 'no-disponible'. */
export async function abrirMenuCompartir(url = typeof window !== 'undefined' ? window.location.origin : '') {
  if (!puedeCompartir()) return 'no-disponible'
  try {
    await navigator.share({ title: 'CuadraMe', url })
    return 'abierto'
  } catch (e) {
    return e?.name === 'AbortError' ? 'cancelado' : 'no-disponible'
  }
}

// «Ya lo vi»: el aviso del Inicio no vuelve a salir en 14 días
const CLAVE = 'cuadrame_aviso_instalar'
const DIAS = 14

export function avisoInstalarCerrado(ahora = Date.now()) {
  try {
    const t = Number(window.localStorage.getItem(CLAVE))
    return !!t && ahora - t < DIAS * 86400000
  } catch {
    return false
  }
}

export function cerrarAvisoInstalar(ahora = Date.now()) {
  try {
    window.localStorage.setItem(CLAVE, String(ahora))
  } catch {
    /* sin almacenamiento: vuelve a salir en la próxima visita */
  }
}
