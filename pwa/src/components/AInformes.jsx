import { Navigate, useLocation } from 'react-router-dom'

// Las pantallas de «cómo voy» (Informe, Mi resumen, Cosas raras, Patrimonio, Cierre) ahora son pestañas de /informes.
// Los enlaces viejos siguen funcionando: llevan a su pestaña y conservan el resto de la consulta (p. ej. el periodo).
export default function AInformes({ tab }) {
  const { search } = useLocation()
  const q = new URLSearchParams(search)
  q.set('tab', tab)
  return <Navigate to={{ pathname: '/informes', search: `?${q.toString()}` }} replace />
}
