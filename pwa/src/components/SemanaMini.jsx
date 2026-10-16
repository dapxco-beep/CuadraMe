import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { rangoPeriodo } from '../lib/informe'

// Los últimos 7 días de gasto en barritas, dentro de la tarjeta de saldo de Inicio. Toda la franja es un
// enlace a «En qué gasto» (donde está el día a día completo). Si no carga o no hay gastos, no ocupa lugar.
const INICIALES = ['D', 'L', 'M', 'X', 'J', 'V', 'S']
const inicialDe = (iso) => INICIALES[new Date(`${iso}T12:00:00`).getDay()]

export default function SemanaMini() {
  const [dias, setDias] = useState(null)

  useEffect(() => {
    let activo = true
    const { desde, hasta } = rangoPeriodo('7_dias')
    // Promise.resolve().then: un fallo (también uno síncrono) cae al catch y la franja simplemente no sale.
    Promise.resolve()
      .then(() => api.gastoDiario(desde, hasta))
      .then((d) => activo && setDias(d?.dias || []))
      .catch(() => activo && setDias([]))
    return () => {
      activo = false
    }
  }, [])

  if (!dias || dias.length === 0 || !dias.some((d) => d.gasto > 0)) return null
  const max = Math.max(...dias.map((d) => d.gasto), 1)

  return (
    <Link to="/informe" aria-label="Tu gasto de los últimos 7 días. Ver día a día" data-testid="semana-mini" className="mt-3 flex items-end gap-1.5 min-h-[44px]">
      {dias.map((d, i) => (
        <span key={d.dia} className="flex-1 flex flex-col items-center gap-1" aria-hidden="true">
          <span
            className={`w-full rounded-sm ${i === dias.length - 1 ? 'bg-white' : 'bg-white/55'}`}
            style={{ height: `${Math.max(3, Math.round((d.gasto / max) * 32))}px` }}
          />
          <span className="text-[10px] opacity-80 leading-none">{inicialDe(d.dia)}</span>
        </span>
      ))}
    </Link>
  )
}
