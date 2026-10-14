// Versión de la app que corre en este dispositivo. Las tres constantes las inyecta Vite en el
// build (vite.config.js); en pruebas y en desarrollo no existen y se usan valores por defecto.
/* global __APP_VERSION__, __APP_BUILD__, __APP_COMMIT__ */
export const APP_VERSION = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '0.0.0'
export const APP_BUILD = typeof __APP_BUILD__ !== 'undefined' ? __APP_BUILD__ : ''
export const APP_COMMIT = typeof __APP_COMMIT__ !== 'undefined' ? __APP_COMMIT__ : 'dev'

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

/** «14 oct 2026 14:26» (hora local) o '' si no hay fecha válida. */
export function fechaCompilacion(iso) {
  const d = new Date(iso)
  if (!iso || Number.isNaN(d.getTime())) return ''
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getDate()} ${MESES[d.getMonth()]} ${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** «CuadraMe 1.0.0 · compilación 14 oct 2026 14:26 · a1b2c3d» */
export function textoVersion(v = { version: APP_VERSION, build: APP_BUILD, commit: APP_COMMIT }) {
  const f = fechaCompilacion(v.build)
  return ['CuadraMe ' + v.version, f && 'compilación ' + f, v.commit].filter(Boolean).join(' · ')
}

/** ¿La compilación publicada es más nueva que la que corre? (sin fecha propia: nunca) */
export function hayVersionNueva(publicada, actual = { build: APP_BUILD, commit: APP_COMMIT }) {
  if (!publicada?.build || !actual.build) return false
  if (publicada.commit && publicada.commit === actual.commit) return false
  return new Date(publicada.build).getTime() > new Date(actual.build).getTime()
}

/** Recarga saltando la caché del shell; no toca los datos de la persona. */
export async function recargarConVersionNueva() {
  try {
    if ('caches' in window) {
      const nombres = await caches.keys()
      await Promise.all(nombres.filter((n) => n.startsWith('cuadrame-shell-')).map((n) => caches.delete(n)))
    }
    const reg = await navigator.serviceWorker?.getRegistration?.()
    await reg?.update?.()
  } catch {
    /* sin caché o sin service worker: igual se recarga */
  }
  window.location.reload()
}

/** Lee /version.json (nunca cacheado). Devuelve null si no se pudo. */
export async function leerVersionPublicada() {
  try {
    const r = await fetch('/version.json?t=' + Date.now(), { cache: 'no-store' })
    if (!r.ok) return null
    const d = await r.json()
    return d && typeof d.build === 'string' ? d : null
  } catch {
    return null
  }
}
