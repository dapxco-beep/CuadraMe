import { useId } from 'react'
import { CheckCircle2, ChevronDown } from 'lucide-react'

// Bloque plegable del centro "Traer movimientos". El contador es lo que falta por resolver ahí;
// en cero el bloque queda en "Todo al día" (sigue abierto o cerrado como lo dejó el usuario).
export default function BloqueCentro({ id, titulo, icono: Icono, cuenta = 0, mostrarAlDia = true, subtitulo, abierto, onToggle, children }) {
  const uid = useId()
  const alDia = cuenta === 0
  return (
    <section id={id} className="mx-6 mt-4 scroll-mt-4 rounded-3xl bg-paper-raised ring-1 ring-line/60 shadow-[0_1px_3px_rgba(34,31,25,0.04)]" data-testid={`bloque-${id}`}>
      <h2>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={abierto}
          aria-controls={`${uid}-cuerpo`}
          className="w-full flex items-center gap-3.5 px-4 py-3.5 min-h-[64px] text-left"
        >
          {Icono && (
            <span className="w-10 h-10 rounded-2xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
              <Icono size={20} strokeWidth={1.75} aria-hidden="true" />
            </span>
          )}
          <span className="flex-1 min-w-0">
            <span className="block text-[15px] font-semibold leading-tight">{titulo}</span>
            {subtitulo && <span className="block text-xs text-ink-soft mt-0.5 truncate">{subtitulo}</span>}
          </span>
          {!alDia && (
            <span className="min-w-[24px] text-center rounded-full bg-accent-soft text-accent text-xs font-bold px-2 py-0.5" aria-label={`${cuenta} por resolver`}>
              {cuenta}
            </span>
          )}
          {alDia && mostrarAlDia && (
            <span className="flex items-center gap-1 text-xs font-semibold text-cuadra" data-testid={`al-dia-${id}`}>
              <CheckCircle2 size={16} aria-hidden="true" /> Todo al día
            </span>
          )}
          <ChevronDown size={16} className={`text-ink-soft shrink-0 motion-safe:transition-transform ${abierto ? 'rotate-180' : ''}`} aria-hidden="true" />
        </button>
      </h2>
      {abierto && (
        <div id={`${uid}-cuerpo`} role="region" aria-label={titulo} className="px-4 pb-5 pt-1 border-t border-line/50">
          {children}
        </div>
      )}
    </section>
  )
}
