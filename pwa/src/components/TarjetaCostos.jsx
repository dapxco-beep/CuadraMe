import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, Receipt } from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { hayCostos, nombreMes, textoVariacion } from '../lib/costos'
import Icono from './Icono'

/**
 * Tarjeta resumen de Inicio: cuánto te costó tener tu plata este mes y este año. Solo se pinta cuando
 * hay datos (intereses, cuotas, comisiones, 4x1000 o rendimientos detectados en tus extractos).
 */
export default function TarjetaCostos({ className = 'mx-6 mt-4' }) {
  const { fmt } = useBloqueo()
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
  const { mes, anio } = datos
  const urgente = (datos.alertas || []).some((a) => a.prioridad === 1)

  return (
    <Link
      to="/costos"
      data-testid="tarjeta-costos"
      className="block"
      aria-label={`Lo que te cuesta tu plata: ${fmt(mes.total)} este mes`}
    >
      <section className={`card-marca bg-paper-raised border border-line p-4 ${className}`}>
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-accent-soft text-accent flex items-center justify-center shrink-0">
            <Icono icono={Receipt} tam="sm" />
          </span>
          <h2 className="t-kicker flex-1">Lo que te cuesta tu plata</h2>
          <Icono icono={ChevronRight} tam="sm" className="text-ink-soft" />
        </div>
        <p className="text-2xl t-display mt-2">{fmt(mes.total)}</p>
        <p className="t-apoyo">en {nombreMes(mes.mes)} · {textoVariacion(mes)}</p>
        <p className="text-xs text-ink-soft mt-2">
          En el año: {fmt(anio.total)}
          {anio.rendimientos > 0 && ` · tu plata te rindió ${fmt(anio.rendimientos)}`}
        </p>
        {urgente && <p className="text-xs font-semibold text-danger mt-2">Hay un cobro por revisar.</p>}
      </section>
    </Link>
  )
}
