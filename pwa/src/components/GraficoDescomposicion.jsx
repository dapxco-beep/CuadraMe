import { formatCOP } from '../lib/format'
import { COMPONENTES_CRECIMIENTO, altoSegmento, escalaDescomposicion } from '../lib/planificacion'
import { etiquetaMes } from '../lib/patrimonio'

// De dónde viene el crecimiento de cada mes: ahorro, valorización de inversiones y
// menos deuda. Barras apiladas; lo negativo (pérdida, más deuda) cuelga hacia abajo.
export default function GraficoDescomposicion({ meses }) {
  if (!meses?.length) return null
  const ultimos = meses.slice(-6)
  const escala = escalaDescomposicion(ultimos)
  const ALTO = 120
  const altoArriba = (escala.pctArriba / 100) * ALTO
  const altoAbajo = ALTO - altoArriba
  const actual = ultimos[ultimos.length - 1]

  return (
    <div data-testid="grafico-descomposicion">
      <div className="flex items-stretch gap-2" style={{ height: ALTO }}>
        {ultimos.map((m) => (
          <div key={m.mes} className="flex-1 flex flex-col min-w-0" role="img"
            aria-label={`${etiquetaMes(m.mes)}: ${formatCOP(m.neto_delta)}`}>
            <div className="flex flex-col-reverse justify-start" style={{ height: altoArriba }}>
              {COMPONENTES_CRECIMIENTO.filter((c) => (m[c.clave] || 0) > 0).map((c) => (
                <div key={c.clave} data-segmento={c.clave}
                  style={{ height: `${altoSegmento(m[c.clave], escala) * (altoArriba / 100)}px`, background: c.color }} />
              ))}
            </div>
            <div className="flex flex-col justify-start" style={{ height: altoAbajo }}>
              {COMPONENTES_CRECIMIENTO.filter((c) => (m[c.clave] || 0) < 0).map((c) => (
                <div key={c.clave} data-segmento={c.clave}
                  style={{ height: `${altoSegmento(m[c.clave], escala) * (altoAbajo / 100)}px`, background: c.color, opacity: 0.55 }} />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-1.5">
        {ultimos.map((m) => (
          <p key={m.mes} className="flex-1 text-center text-[11px] text-ink-soft">{etiquetaMes(m.mes)}</p>
        ))}
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3">
        {COMPONENTES_CRECIMIENTO.map((c) => (
          <span key={c.clave} className="flex items-center gap-1.5 text-xs text-ink-soft">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: c.color }} />
            {c.etiqueta}
            <span className="font-semibold text-ink">{formatCOP(actual[c.clave] || 0)}</span>
          </span>
        ))}
      </div>
      <p className="text-[11px] text-ink-soft mt-2">
        Último mes ({etiquetaMes(actual.mes)}): tu patrimonio cambió {formatCOP(actual.neto_delta)}.
      </p>
    </div>
  )
}
