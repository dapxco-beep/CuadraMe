import { useEffect, useState } from 'react'
import { api } from './api'

// Lectura de GET /informes/evolucion-categorias con caché corta en memoria (60 s) para no repetir la misma
// consulta entre el listado con tendencias y la vista evolutiva. La lógica de cifras vive en el servidor.
const TTL = 60_000
const cache = new Map()

export function limpiarCacheEvolucion() {
  cache.clear()
}

function pedir(meses, categoria) {
  const clave = `${meses}|${categoria || ''}`
  const hit = cache.get(clave)
  if (hit && Date.now() - hit.t < TTL) return hit.p
  const p = Promise.resolve()
    .then(() => api.evolucionCategorias({ meses, ...(categoria ? { categoria } : {}) }))
    .catch((e) => { cache.delete(clave); throw e })
  cache.set(clave, { t: Date.now(), p })
  return p
}

/** {datos, cargando, error}. `categoria` es opcional (agrega la serie por subcategoría). */
export function useEvolucionCategorias(meses, categoria = null, activo = true) {
  const [estado, setEstado] = useState({ datos: null, cargando: true, error: false })
  useEffect(() => {
    if (!activo) return undefined
    let vivo = true
    setEstado((e) => ({ ...e, cargando: true, error: false }))
    pedir(meses, categoria)
      .then((datos) => vivo && setEstado({ datos, cargando: false, error: false }))
      .catch(() => vivo && setEstado({ datos: null, cargando: false, error: true }))
    return () => { vivo = false }
  }, [meses, categoria, activo])
  return estado
}
