// Recibe lo que otra app compartió con CuadraMe (Android/Chrome). El service worker lo dejó en un
// caché local (public/sw.js); aquí se lee UNA vez, se vuelve a validar y se borra, se use o no.
// Nada se sube solo: la lista precargada espera a que la persona toque «Procesar».
import { validarSeleccion } from './subidaMultiple'

export const CACHE_COMPARTIDO = 'cuadrame-compartido'
const VIGENCIA_MS = 60 * 60 * 1000 // igual que public/compartido-logica.js

/** Lee los archivos pendientes (vigentes y válidos) y vacía el caché. Nunca lanza. */
export async function tomarCompartidos({ cacheStorage = globalThis.caches, ahora = Date.now() } = {}) {
  if (!cacheStorage) return { archivos: [], rechazados: [] }
  try {
    const cache = await cacheStorage.open(CACHE_COMPARTIDO)
    const claves = await cache.keys()
    const archivos = []
    for (const clave of claves) {
      const resp = await cache.match(clave)
      if (!resp) continue
      const guardado = Number(resp.headers.get('x-guardado'))
      if (!(ahora - guardado >= 0 && ahora - guardado <= VIGENCIA_MS)) continue
      let nombre = 'archivo'
      try {
        nombre = decodeURIComponent(resp.headers.get('x-nombre') || 'archivo')
      } catch {}
      const blob = await resp.blob()
      archivos.push(new File([blob], nombre, { type: blob.type }))
    }
    // Se limpia siempre: lo compartido no se queda guardado en el teléfono.
    await Promise.all(claves.map((c) => cache.delete(c)))
    const { aceptados, rechazados } = validarSeleccion(archivos)
    return { archivos: aceptados, rechazados }
  } catch {
    return { archivos: [], rechazados: [] }
  }
}
