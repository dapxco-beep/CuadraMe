import { ArrowDownRight, ArrowUpRight, TrendingUp } from 'lucide-react'
import { pctTexto } from '../../lib/informe'

// Proyección simple del cierre del mes: lo gastado hasta hoy, al mismo ritmo, hasta el último día.
export function proyeccionMes(total, hoy = new Date()) {
  const dia = hoy.getDate()
  const diasMes = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0).getDate()
  if (!total || dia < 3 || dia >= diasMes) return null
  return Math.round((total / dia) * diasMes)
}

function Chip({ pct, titulo }) {
  if (pct === null || pct === undefined) return <span className="text-[11px] text-ink-soft">sin base para comparar</span>
  const sube = pct > 0
  const Icono = sube ? ArrowUpRight : ArrowDownRight
  return (
    <span
      title={titulo}
      className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[11px] font-bold ${
        pct === 0 ? 'bg-line text-ink-soft' : sube ? 'bg-danger/10 text-danger' : 'bg-cuadra/10 text-cuadra'
      }`}
    >
      {pct !== 0 && <Icono size={14} aria-hidden="true" />}
      {pctTexto(pct)}
    </span>
  )
}

function Ficha({ etiqueta, valor, tono }) {
  return (
    <div className="rounded-2xl bg-paper border border-line px-3 py-2.5 min-w-0">
      <p className="text-xs uppercase tracking-wide text-ink-soft">{etiqueta}</p>
      <p className={`text-sm font-bold mt-0.5 truncate ${tono || ''}`}>{valor}</p>
    </div>
  )
}

/** Tarjeta principal: cuánto gastaste, cómo va contra el periodo anterior, la proyección y la foto ingresos/ahorro. */
export default function HeroGasto({ informe, fmt, esMesActual, className = '' }) {
  const prom = informe.total_anterior || 0
  const tope = Math.max(informe.total, prom, 1)
  const proy = esMesActual ? proyeccionMes(informe.total) : null
  const tasa = informe.ingresos > 0 ? Math.round((informe.ahorro / informe.ingresos) * 100) : null
  const sinBase = esMesActual && informe.variacion_pct === -100 && !informe.total

  return (
    <section className={`card-marca bg-paper-raised border border-line p-4 ${className}`} aria-label="Resumen del periodo">
      <p className="t-kicker text-ink-soft capitalize">Gastaste en {informe.etiqueta}</p>
      <div className="flex items-end justify-between gap-3 mt-1">
        <p className="text-[34px] leading-none t-display">{fmt(informe.total)}</p>
        {sinBase ? <span className="text-xs text-ink-soft pb-1">El mes apenas empieza</span> : <Chip pct={informe.variacion_pct} titulo={informe.anterior.etiqueta} />}
      </div>
      <p className="text-xs text-ink-soft mt-1.5">
        frente a {informe.anterior.etiqueta} ({fmt(informe.total_anterior)})
      </p>

      <div className="mt-3 space-y-1.5" aria-hidden="true">
        <div className="flex items-center gap-2 text-[11px]">
          <span className="w-12 shrink-0 text-ink-soft">Ahora</span>
          <span className="flex-1 h-2.5 rounded-full bg-line overflow-hidden"><span className="block h-full rounded-full bg-brand" style={{ width: `${(informe.total / tope) * 100}%` }} /></span>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="w-12 shrink-0 text-ink-soft">Antes</span>
          <span className="flex-1 h-2.5 rounded-full bg-line overflow-hidden"><span className="block h-full rounded-full bg-ink-soft/50" style={{ width: `${(prom / tope) * 100}%` }} /></span>
        </div>
      </div>

      {proy && (
        <p className="mt-3 flex items-start gap-2 rounded-xl bg-accent-soft px-3 py-2 text-xs">
          <TrendingUp size={16} className="shrink-0 mt-0.5 text-accent" aria-hidden="true" />
          <span>
            A este ritmo cerrarías el mes en <strong>{fmt(proy)}</strong>
            {prom > 0 && <> ({proy > prom ? `${fmt(proy - prom)} más` : `${fmt(prom - proy)} menos`} que el mes anterior)</>}.
          </span>
        </p>
      )}

      {informe.ingresos > 0 && (
        <div className="grid grid-cols-3 gap-2 mt-3">
          <Ficha etiqueta="Ingresos" valor={fmt(informe.ingresos)} />
          <Ficha etiqueta={informe.ahorro >= 0 ? 'Te sobró' : 'Te faltó'} valor={fmt(Math.abs(informe.ahorro))} tono={informe.ahorro >= 0 ? 'text-cuadra' : 'text-danger'} />
          <Ficha etiqueta="Ahorro" valor={tasa === null ? '—' : `${tasa} %`} tono={tasa !== null && tasa < 0 ? 'text-danger' : ''} />
        </div>
      )}
    </section>
  )
}
