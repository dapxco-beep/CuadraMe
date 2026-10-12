import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, Receipt } from 'lucide-react'
import { api } from '../lib/api'
import { hayCostos } from '../lib/costos'
import Icono from './Icono'

/**
 * Enlace discreto a «Lo que te cuesta tu plata» (/costos). Solo aparece cuando ya hay cobros o
 * rendimientos detectados; si no hay datos, falla la carga o la persona está en modo sin conexión,
 * no pinta nada. Sin entrada propia en el menú: se llega desde Cuentas, Informes e Inicio.
 */
export default function EnlaceCostos({ className = 'mx-6 mt-3' }) {
  const [datos, setDatos] = useState(null)

  useEffect(() => {
    let activo = true
    Promise.resolve()
      .then(() => api.costosBancarios?.())
      .then((d) => activo && setDatos(d))
      .catch(() => {})
    return () => {
      activo = false
    }
  }, [])

  if (!hayCostos(datos)) return null
  return (
    <Link
      to="/costos"
      data-testid="enlace-costos"
      className={`flex items-center gap-3 rounded-2xl bg-paper-raised border border-line px-4 min-h-[56px] ${className}`}
    >
      <span className="w-9 h-9 rounded-full bg-accent-soft text-accent flex items-center justify-center shrink-0">
        <Icono icono={Receipt} tam="md" />
      </span>
      <span className="flex-1 text-sm font-semibold">Lo que te cuesta tu plata</span>
      <Icono icono={ChevronRight} tam="sm" className="text-ink-soft" />
    </Link>
  )
}
