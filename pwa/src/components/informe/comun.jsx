import { useId, useState } from 'react'
import { ArrowDownRight, ArrowUpRight, CircleHelp, Minus } from 'lucide-react'
import { formatPorcentaje } from '../../lib/format'

/**
 * Panel de Informes: título, la PREGUNTA que responde y un «¿cómo se calcula?» plegable.
 * Todos los paneles nuevos lo usan para que se lean igual (mismo lenguaje que «Gastos»).
 */
export function Panel({ icono: Ico, titulo, pregunta, info, children, className = '', accion = null }) {
  const [abierto, setAbierto] = useState(false)
  const idInfo = useId()
  return (
    <section className={`card-marca bg-paper-raised border border-line p-4 ${className}`} aria-label={titulo}>
      <div className="flex items-start gap-2">
        {Ico && <Ico size={16} className="text-ink-soft mt-1 shrink-0" aria-hidden="true" />}
        <div className="flex-1 min-w-0">
          <h2 className="text-[15px] font-semibold leading-tight">{titulo}</h2>
          {pregunta && <p className="text-xs text-ink-soft mt-0.5 leading-snug">{pregunta}</p>}
        </div>
        {accion}
        {info && (
          <button
            type="button"
            aria-expanded={abierto}
            aria-controls={idInfo}
            aria-label={`¿Cómo se calcula «${titulo}»?`}
            onClick={() => setAbierto((v) => !v)}
            className={`min-h-11 min-w-11 -mt-2.5 -mr-2.5 shrink-0 flex items-center justify-center rounded-full ${abierto ? 'text-accent' : 'text-ink-soft'}`}
          >
            <CircleHelp size={18} aria-hidden="true" />
          </button>
        )}
      </div>
      {abierto && (
        <p id={idInfo} className="mt-2 rounded-xl bg-paper border border-line p-3 text-xs text-ink-soft leading-relaxed">
          {info}
        </p>
      )}
      <div className="mt-3">{children}</div>
    </section>
  )
}

/** «en octubre de 2026», «durante los últimos 3 meses», «en el periodo del 1 al 15 de junio» (igual que el servidor). */
export function enPeriodo(etiqueta) {
  if (etiqueta.startsWith('del ')) return `en el periodo ${etiqueta}`
  if (/^(los|el|la) /.test(etiqueta)) return `durante ${etiqueta}`
  return `en ${etiqueta}`
}

const num = (n) => String(n).replace('.', ',')

/**
 * Cambio contra el periodo anterior. Nunca depende solo del color: lleva flecha, signo y una frase para lectores
 * de pantalla. `mejorSube`: ¿subir es bueno? (ingresos sí, gastos no). `puntos`: cambio en puntos porcentuales
 * (para la tasa de ahorro). Un periodo recién empezado (valor 0) no muestra un «−100 %» que solo es ruido.
 */
export function Cambio({ pct, mejorSube = true, actual, puntos = false, className = '' }) {
  if (actual === 0 && pct !== null && pct !== undefined) return null
  if (pct === null || pct === undefined) {
    return <span className={`text-[11px] text-ink-soft ${className}`}>sin base para comparar</span>
  }
  const sube = pct > 0
  const igual = pct === 0
  const bueno = igual ? null : sube === mejorSube
  const Flecha = igual ? Minus : sube ? ArrowUpRight : ArrowDownRight
  const texto = puntos ? `${sube ? '+' : igual ? '' : '−'}${num(Math.abs(pct))} pts` : formatPorcentaje(pct, { signo: true })
  const frase = igual
    ? 'igual que el periodo anterior'
    : `${sube ? 'sube' : 'baja'} ${num(Math.abs(pct))}${puntos ? ' puntos' : ' %'} frente al periodo anterior`
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${bueno === null ? 'text-ink-soft' : bueno ? 'text-cuadra' : 'text-danger'} ${className}`}
    >
      <Flecha size={14} aria-hidden="true" />
      <span aria-hidden="true">{texto}</span>
      <span className="sr-only">{frase}</span>
    </span>
  )
}

export const pctSimple = (v) => (v === null || v === undefined ? '—' : `${num(Math.round(v * 10) / 10)} %`)
export const conSigno = (v, fmt) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmt(Math.abs(v))}`
