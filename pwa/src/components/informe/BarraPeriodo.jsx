import { CalendarRange } from 'lucide-react'
import SelectorPeriodo from '../SelectorPeriodo'
import { etiquetaRango } from '../../lib/informe'
import { MAX_DIAS_PERSONALIZADO, PERIODOS_INFORMES, usePeriodoInforme } from '../../lib/periodoInforme'

/**
 * El ÚNICO selector de periodo de Informes: lo que elijas aquí manda en todas las pestañas (Resumen, Gastos, Mi mes, Días,
 * Patrimonio, Cierre e Impuestos). Vive en la dirección de la página, así que se conserva al cambiar de pestaña.
 */
export default function BarraPeriodo({ className = '' }) {
  const p = usePeriodoInforme()
  if (!p) return null
  const { valor, setValor } = p
  return (
    <section aria-label="Periodo del informe" className={className}>
      <div className="rounded-2xl border border-line bg-paper-raised px-3 pt-2.5 pb-2">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
          <p className="flex items-center gap-1.5 text-sm font-semibold" aria-live="polite">
            <CalendarRange size={16} className="shrink-0 self-center text-accent" aria-hidden="true" />
            <span className="sr-only">Mostrando </span>
            <span>{etiquetaRango(valor.desde, valor.hasta)}</span>
          </p>
          <p className="text-[11px] text-ink-soft">Aplica a todas las pestañas</p>
        </div>
        <div className="mt-2">
          <SelectorPeriodo
            opciones={PERIODOS_INFORMES}
            valor={valor}
            onChange={setValor}
            maxDias={MAX_DIAS_PERSONALIZADO}
            etiqueta="Periodo del informe"
            desplazable
          />
        </div>
      </div>
    </section>
  )
}
