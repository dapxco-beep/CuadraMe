import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

// ¿Hay una pantalla anterior DENTRO de la app a la que "atrás" pueda volver?
// Por qué no basta navigate(-1): si el usuario entra por un enlace directo, recarga,
// toca una notificación push o abre el enlace del atajo, atrás lo sacaría de la app
// (o no haría nada). react-router guarda en history.state un índice (idx) que vale 0
// en la primera entrada de la sesión; en routers sin ese índice (MemoryRouter) la
// primera ubicación tiene key === 'default'.
export function hayHistorialInterno(location) {
  const idx = typeof window !== 'undefined' ? window.history.state?.idx : undefined
  if (typeof idx === 'number') return idx > 0
  return location.key !== 'default'
}

// useVolver('/perfil') -> función para el botón "Volver".
//  - con historial interno: navigate(-1) (vuelve a donde estaba el usuario)
//  - sin historial: va a la ruta lógica por defecto, con replace para no dejar la
//    pantalla actual en el historial.
export function useVolver(rutaPorDefecto = '/') {
  const navigate = useNavigate()
  const location = useLocation()
  return useCallback(() => {
    if (hayHistorialInterno(location)) navigate(-1)
    else navigate(rutaPorDefecto, { replace: true })
  }, [navigate, location, rutaPorDefecto])
}
