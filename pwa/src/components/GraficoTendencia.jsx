import { useState } from 'react'
import { formatCOP } from '../lib/format'

const MESES_CORTOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

function etiquetaMes(clave) {
  const [, mes] = clave.split('-')
  return MESES_CORTOS[parseInt(mes, 10) - 1]
}

export default function GraficoTendencia({ meses }) {
  const [hover, setHover] = useState(null)
  if (!meses.length) return null

  const maxValor = Math.max(1, ...meses.flatMap((m) => [m.ingresos, m.gastos]))
  const alturaChart = 140
  const anchoGrupo = 100 / meses.length
  const anchoBarra = Math.min(14, anchoGrupo * 0.28)

  return (
    <div className="relative">
      <svg viewBox={`0 0 100 ${alturaChart + 24}`} className="w-full" style={{ height: 180 }} preserveAspectRatio="none">
        {meses.map((m, i) => {
          const cx = anchoGrupo * i + anchoGrupo / 2
          const hIngreso = (m.ingresos / maxValor) * alturaChart
          const hGasto = (m.gastos / maxValor) * alturaChart
          const activo = hover === i

          return (
            <g key={m.mes}>
              <rect
                x={cx - anchoBarra - 1}
                y={alturaChart - hIngreso}
                width={anchoBarra}
                height={hIngreso}
                rx={2}
                fill="var(--color-accent)"
                opacity={hover === null || activo ? 1 : 0.35}
              />
              <rect
                x={cx + 1}
                y={alturaChart - hGasto}
                width={anchoBarra}
                height={hGasto}
                rx={2}
                fill="var(--color-ink)"
                opacity={hover === null || activo ? 1 : 0.35}
              />
              <rect
                x={anchoGrupo * i}
                y={0}
                width={anchoGrupo}
                height={alturaChart}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                onTouchStart={() => setHover(i)}
              />
              <text
                x={cx}
                y={alturaChart + 16}
                textAnchor="middle"
                fontSize="7"
                fill="var(--color-ink-soft)"
              >
                {etiquetaMes(m.mes)}
              </text>
            </g>
          )
        })}
      </svg>

      {hover !== null && (
        <div className="absolute top-0 left-0 right-0 flex justify-center pointer-events-none">
          <div className="bg-ink text-paper text-xs rounded-xl px-3 py-2 shadow-lg">
            <p className="font-semibold">{etiquetaMes(meses[hover].mes)}</p>
            <p>Ingresos {formatCOP(meses[hover].ingresos)}</p>
            <p>Gastos {formatCOP(meses[hover].gastos)}</p>
          </div>
        </div>
      )}

      <div className="flex items-center gap-4 mt-2 justify-center">
        <span className="flex items-center gap-1.5 text-xs text-ink-soft">
          <span className="w-2.5 h-2.5 rounded-full bg-accent" /> Ingresos
        </span>
        <span className="flex items-center gap-1.5 text-xs text-ink-soft">
          <span className="w-2.5 h-2.5 rounded-full bg-ink" /> Gastos
        </span>
      </div>
    </div>
  )
}
