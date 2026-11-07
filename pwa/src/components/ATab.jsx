import { Navigate, useLocation } from 'react-router-dom'

// Redirige una ruta vieja a la pestaña de su pantalla nueva y conserva el resto de la consulta (p. ej. el periodo).
export default function ATab({ a, tab }) {
  const { search } = useLocation()
  const q = new URLSearchParams(search)
  q.set('tab', tab)
  return <Navigate to={{ pathname: a, search: `?${q.toString()}` }} replace />
}
