import { useId } from 'react'
import { CheckCircle2, ChevronDown } from 'lucide-react'

// Bloque plegable del centro "Traer movimientos". El contador es lo que falta por resolver ahí;
// en cero el bloque queda en "Todo al día" (sigue abierto o cerrado como lo dejó el usuario).
export default function BloqueCentro({ id, titulo, icono: Icono, cuenta = 0, mostrarAlDia = true, abierto, onToggle, children }) {
  const uid = useId()
  const alDia = cuenta === 0
  return (
    <section id={id} className="mx-6 mt-4 scroll-mt-4 rounded-2xl bg-paper-raised border border-line" data-testid={`bloque-${id}`}>
      <h2>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={abierto}
          aria-controls={`${uid}-cuerpo`}
          className="w-full flex items-center gap-3 px-4 min-h-[56px] text-left"
        >
          {Icono && <Icono size={18} className="text-accent shrink-0" aria-hidden="true" />}
          <span className="flex-1 text-[15px] font-semibold">{titulo}</span>
          {!alDia && (
            <span className="min-w-[22px] text-center rounded-full bg-accent text-white text-xs font-bold px-2 py-0.5" aria-label={`${cuenta} por resolver`}>
              {cuenta}
            </span>
          )}
          {alDia && mostrarAlDia && (
            <span className="flex items-center gap-1 text-xs font-semibold text-cuadra" data-testid={`al-dia-${id}`}>
              <CheckCircle2 size={16} aria-hidden="true" /> Todo al día
            </span>
          )}
          <ChevronDown size={16} className={`text-ink-soft shrink-0 transition-transform ${abierto ? 'rotate-180' : ''}`} aria-hidden="true" />
        </button>
      </h2>
      {abierto && (
        <div id={`${uid}-cuerpo`} role="region" aria-label={titulo} className="px-4 pb-4">
          {children}
        </div>
      )}
    </section>
  )
}
