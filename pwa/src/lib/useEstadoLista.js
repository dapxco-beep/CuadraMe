import { useEffect, useLayoutEffect, useRef } from 'react'

// Recordar dónde estaba el usuario en una lista al navegar a un detalle y volver.
//
// El problema: al abrir un movimiento (o una meta, una deuda...) la lista se desmonta; al volver
// se monta de cero y el usuario queda arriba del todo, sin filtros y con solo la primera página.
// La solución se reparte en tres capas, de la más barata a la más robusta:
//   1. Los FILTROS viven en la URL (query params): sobreviven a atrás, a recargar y a compartir.
//   2. Aquí: la POSICIÓN de scroll y CUÁNTOS elementos había cargados, en sessionStorage
//      (clave = ruta + filtros). Sobrevive a recargar la pestaña; muere al cerrarla.
//   3. Un caché en memoria de los elementos ya cargados (para pintar la lista al instante al
//      volver y revalidar en segundo plano) que el detalle PARCHEA al guardar o eliminar, así la
//      lista refleja el cambio sin recargarse entera.
// Todo acceso a sessionStorage va en try/catch (modo privado, almacenamiento bloqueado...).

const PREFIJO = 'cuadrame:lista:'

export function leerEstadoLista(clave) {
  try {
    const crudo = window.sessionStorage.getItem(PREFIJO + clave)
    return crudo ? JSON.parse(crudo) : null
  } catch {
    return null
  }
}

export function guardarEstadoLista(clave, estado) {
  try {
    window.sessionStorage.setItem(PREFIJO + clave, JSON.stringify(estado))
  } catch {
    /* sin almacenamiento: la lista simplemente vuelve arriba */
  }
}

/**
 * useEstadoLista(clave, { contenedorRef, cantidad, listo })
 *  - clave: identifica la lista (ruta + filtros). Si cambia la URL, es otra lista.
 *  - contenedorRef: el elemento que hace scroll (si la página entera hace scroll también se guarda).
 *  - cantidad: cuántos elementos hay cargados ahora (para pedirlos todos de nuevo al volver).
 *  - listo: true cuando la lista ya se pintó con datos; recién entonces se restaura el scroll.
 * Devuelve el estado guardado al montar ({ scroll, ventana, cantidad } o null).
 */
export function useEstadoLista(clave, { contenedorRef, cantidad = 0, listo = true } = {}) {
  const guardado = useRef(undefined)
  if (guardado.current === undefined) guardado.current = leerEstadoLista(clave)

  const listoRef = useRef(listo)
  const cantidadRef = useRef(cantidad)
  const restaurado = useRef(false)
  listoRef.current = listo
  cantidadRef.current = cantidad

  function instantanea() {
    const el = contenedorRef?.current
    return {
      scroll: el ? el.scrollTop : 0,
      ventana: typeof window !== 'undefined' ? window.scrollY || 0 : 0,
      cantidad: cantidadRef.current,
    }
  }

  // Restaurar la posición cuando la lista ya está pintada (antes de que el navegador dibuje,
  // para que no se vea el salto desde arriba)
  useLayoutEffect(() => {
    if (!listo || restaurado.current) return
    restaurado.current = true
    const g = guardado.current
    if (!g) return
    const el = contenedorRef?.current
    if (el && g.scroll) el.scrollTop = g.scroll
    if (g.ventana && typeof window.scrollTo === 'function') window.scrollTo(0, g.ventana)
  }, [listo, contenedorRef])

  // Guardar al hacer scroll (con requestAnimationFrame para no escribir en cada píxel).
  // El evento scroll no burbujea: se escucha en captura sobre document para cubrir tanto el
  // contenedor de la pantalla como la ventana.
  useEffect(() => {
    let pendiente = false
    const guardar = () => {
      pendiente = false
      if (listoRef.current && restaurado.current) guardarEstadoLista(clave, instantanea())
    }
    const alScroll = () => {
      if (pendiente || !listoRef.current || !restaurado.current) return
      pendiente = true
      requestAnimationFrame(guardar)
    }
    document.addEventListener('scroll', alScroll, true)
    return () => {
      document.removeEventListener('scroll', alScroll, true)
      // Al irse de la pantalla (p. ej. a un detalle) se deja la última posición conocida
      if (listoRef.current && restaurado.current) {
        const previo = leerEstadoLista(clave)
        guardarEstadoLista(clave, { ...instantanea(), scroll: previo?.scroll ?? instantanea().scroll, ventana: previo?.ventana ?? instantanea().ventana })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave])

  // Si cambia la cantidad cargada ("cargar más"), se actualiza sin tocar el scroll guardado
  useEffect(() => {
    if (!listo || !restaurado.current) return
    const previo = leerEstadoLista(clave) || instantanea()
    guardarEstadoLista(clave, { ...previo, cantidad })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cantidad, listo, clave])

  return guardado.current
}

// --- Caché en memoria de los elementos de una lista --------------------------------------

const cache = new Map() // clave -> { items, hayMas }
const MAX_ENTRADAS = 8

export function leerCacheLista(clave) {
  return cache.get(clave) || null
}

export function guardarCacheLista(clave, datos) {
  cache.delete(clave)
  cache.set(clave, datos)
  while (cache.size > MAX_ENTRADAS) cache.delete(cache.keys().next().value)
}

/** El detalle guardó un cambio: se parchea ese elemento en todas las listas en caché. */
export function parchearEnCaches(elemento, campoId = 'id') {
  for (const [k, v] of cache) {
    if (v.items.some((x) => x[campoId] === elemento[campoId])) {
      cache.set(k, { ...v, items: v.items.map((x) => (x[campoId] === elemento[campoId] ? { ...x, ...elemento } : x)) })
    }
  }
}

/** El detalle eliminó el elemento: se quita de todas las listas en caché. */
export function quitarDeCaches(id, campoId = 'id') {
  for (const [k, v] of cache) {
    if (v.items.some((x) => x[campoId] === id)) {
      cache.set(k, { ...v, items: v.items.filter((x) => x[campoId] !== id) })
    }
  }
}

export function vaciarCachesListas() {
  cache.clear()
}
