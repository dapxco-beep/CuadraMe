import { useEffect, useState } from 'react'
import { formatCOP } from '../lib/format'
import { arcosDona, CLASES, formatPct } from '../lib/patrimonio'

const RADIO = 40

// Dona de distribución por clase de activo. Los arcos "crecen" al montarse
// (transición del trazo) salvo que el usuario prefiera menos movimiento.
export default function DonaDistribucion({ distribucion }) {
  const [listo, setListo] = useState(false)
  useEffect(() => {
    const t = requestAnimationFrame(() => setListo(true))
    return () => cancelAnimationFrame(t)
  }, [])

  if (!distribucion.length) return null
  const arcos = arcosDona(distribucion, RADIO)
  const total = distribucion.reduce((s, d) => s + d.valor, 0)

  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 100 100" className="w-32 h-32 shrink-0 -rotate-90" role="img" aria-label="Distribución del patrimonio por clase">
        <circle cx="50" cy="50" r={RADIO} fill="none" stroke="var(--color-line)" strokeWidth="14" />
        {arcos.map((a) => (
          <circle
            key={a.clase}
            cx="50"
            cy="50"
            r={RADIO}
            fill="none"
            stroke={a.color}
            className="dona-trazo"
            strokeWidth="14"
            strokeDasharray={`${listo ? a.largo : 0} ${listo ? a.resto : 2 * Math.PI * RADIO}`}
            strokeDashoffset={a.desplazamiento}
            style={{ transition: 'stroke-dasharray 0.9s cubic-bezier(0.22, 1, 0.36, 1)' }}
          />
        ))}
      </svg>
      <ul className="flex-1 space-y-1.5 min-w-0">
        {distribucion.map((d, i) => (
          <li key={d.clase} className="flex items-center gap-2 text-xs">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: arcos[i].color }} />
            <span className="flex-1 truncate">{CLASES[d.clase]?.label || d.clase}</span>
            <span className="text-ink-soft tabular-nums">{formatPct(d.pct, 0).replace('+', '')}</span>
          </li>
        ))}
        <li className="pt-1 border-t border-line text-[11px] text-ink-soft">Total {formatCOP(total)}</li>
      </ul>
    </div>
  )
}
