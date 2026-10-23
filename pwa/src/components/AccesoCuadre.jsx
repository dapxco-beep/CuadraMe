import { Link } from 'react-router-dom'
import { ChevronRight, ShieldCheck } from 'lucide-react'
import Icono from './Icono'
import { useAutoarreglo } from '../lib/autoarreglo'
import { resumenCuadre, vistasCuadre } from '../lib/miCuentaCuadra'

/** Acceso discreto desde Inicio a «Mi cuenta cuadra». Solo sale cuando ya hay algo que contar (no ocupa sitio vacío). */
export default function AccesoCuadre({ className = '' }) {
  const a = useAutoarreglo()
  const vistas = vistasCuadre(a.cuadre)
  if (vistas.length === 0) return null
  const pendientes = vistas.filter((v) => v.estado === 'no_cuadra').length
  return (
    <Link
      to="/mi-cuenta-cuadra" data-testid="acceso-cuadre"
      className={`mx-6 flex min-h-11 items-center gap-2 rounded-2xl bg-paper-raised px-3 text-sm ring-1 ring-line/60 ${className}`}
    >
      <Icono icono={ShieldCheck} tam="sm" className={pendientes ? 'text-accent' : 'text-cuadra'} />
      <span className="flex-1 font-semibold">{resumenCuadre(vistas)}</span>
      <span className="flex items-center gap-1 text-xs font-semibold text-accent">
        Ver
        <Icono icono={ChevronRight} tam="sm" />
      </span>
    </Link>
  )
}
