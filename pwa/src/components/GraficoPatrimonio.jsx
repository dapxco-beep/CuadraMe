import { useState } from 'react'
import { formatCOP } from '../lib/format'
import { etiquetaMes, puntosSerie, trazoArea, trazoLinea } from '../lib/patrimonio'

// Evolución mensual del patrimonio neto: línea + área. Con un solo mes muestra
// un punto y un mensaje, porque la serie se va llenando mes a mes.
export default function GraficoPatrimonio({ historial }) {
  const [hover, setHover] = useState(null)
  if (!historial.length) return null

  const ALTO = 60
  const valores = historial.map((h) => h.patrimonio_neto)
  const puntos = puntosSerie(valores, 100, ALTO)
  const activo = hover ?? puntos.length - 1

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 100 ${ALTO}`}
        className="w-full"
        style={{ height: 160 }}
        preserveAspectRatio="none"
        role="img"
        aria-label="Evolución del patrimonio neto por mes"
      >
        <defs>
          <linearGradient id="grad-patrimonio" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.28" />
            <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {puntos.length > 1 && (
          <>
            <path d={trazoArea(puntos, ALTO)} fill="url(#grad-patrimonio)" />
            <path
              d={trazoLinea(puntos)}
              fill="none"
              stroke="var(--color-accent)"
              strokeWidth="1.6"
              strokeLinejoin="round"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
              pathLength="1"
              className="linea-patrimonio"
            />
          </>
        )}
        {puntos.map((p, i) => (
          <g key={historial[i].mes}>
            <rect
              x={p.x - 50 / puntos.length}
              y={0}
              width={100 / puntos.length}
              height={ALTO}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onTouchStart={() => setHover(i)}
            />
          </g>
        ))}
      </svg>
      {/* Los puntos van fuera del SVG estirado para que no se deformen en elipse */}
      <div className="absolute inset-x-0 top-0 pointer-events-none" style={{ height: 160 }}>
        {puntos.map((p, i) => (
          <span
            key={historial[i].mes}
            className="absolute rounded-full bg-accent -translate-x-1/2 -translate-y-1/2 transition-all duration-200"
            style={{
              left: `${p.x}%`,
              top: `${(p.y / ALTO) * 100}%`,
              width: i === activo ? 10 : 6,
              height: i === activo ? 10 : 6,
              boxShadow: i === activo ? '0 0 0 4px color-mix(in srgb, var(--color-accent) 25%, transparent)' : 'none',
            }}
          />
        ))}
      </div>

      <div className="flex justify-between mt-1 px-1">
        {historial.length > 1 ? (
          <>
            <span className="text-[11px] text-ink-soft">{etiquetaMes(historial[0].mes)}</span>
            <span className="text-[11px] text-ink-soft">{etiquetaMes(historial[historial.length - 1].mes)}</span>
          </>
        ) : (
          <span className="text-[11px] text-ink-soft mx-auto">
            Tu historial se irá dibujando mes a mes
          </span>
        )}
      </div>

      <p className="text-center text-xs text-ink-soft mt-2" aria-live="polite">
        {etiquetaMes(historial[activo].mes)} · <span className="font-semibold text-ink">{formatCOP(valores[activo])}</span>
      </p>
    </div>
  )
}
