import { useEffect, useState } from 'react'

// Los puntos de corte son los de Tailwind (md = 768, lg = 1024) y deben coincidir con
// los @media de index.css (.app-shell). "movil" = teléfono (barra inferior),
// "riel" = iPad vertical (riel de 72 px), "lateral" = iPad horizontal y PC (barra de 240 px).
export const CONSULTA_RIEL = '(min-width: 768px)'
export const CONSULTA_LATERAL = '(min-width: 1024px)'

function leerModo() {
  if (typeof window === 'undefined' || !window.matchMedia) return 'movil'
  if (window.matchMedia(CONSULTA_LATERAL).matches) return 'lateral'
  if (window.matchMedia(CONSULTA_RIEL).matches) return 'riel'
  return 'movil'
}

export function useModoPantalla() {
  const [modo, setModo] = useState(leerModo)
  useEffect(() => {
    if (!window.matchMedia) return
    const listas = [window.matchMedia(CONSULTA_RIEL), window.matchMedia(CONSULTA_LATERAL)]
    const actualizar = () => setModo(leerModo())
    listas.forEach((m) => m.addEventListener?.('change', actualizar))
    actualizar()
    return () => listas.forEach((m) => m.removeEventListener?.('change', actualizar))
  }, [])
  return modo
}
