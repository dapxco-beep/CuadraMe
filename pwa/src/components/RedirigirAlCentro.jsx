import { Navigate, useLocation } from 'react-router-dom'
import { destinoRedireccion } from '../lib/centro'

// Las rutas viejas (/correos, /conciliacion, /importar, /conexiones) siguen existiendo para no
// romper enlaces, notificaciones push, atajos ni el regreso de Google (?gmail=...): llevan al
// centro "Traer movimientos" con state que dice qué bloque abrir.
export default function RedirigirAlCentro({ ruta }) {
  const location = useLocation()
  const { to, state } = destinoRedireccion(ruta, location)
  return <Navigate to={to} state={state} replace />
}
