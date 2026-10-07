import { Check } from 'lucide-react'
import { PASOS } from '../lib/centro'

// Conecta -> Trae -> Revisa: solo se muestra cuando todavía no hay datos.
export default function PasosCentro({ paso }) {
  return (
    <ol className="flex items-center gap-2 mx-6 mt-3 text-xs" aria-label="Pasos" data-testid="pasos">
      {PASOS.map((t, i) => {
        const n = i + 1
        const hecho = n < paso
        const actual = n === paso
        return (
          <li key={t} className="flex items-center gap-1.5 min-w-0" aria-current={actual ? 'step' : undefined}>
            <span
              className={`w-5 h-5 rounded-full text-[11px] font-bold flex items-center justify-center shrink-0 ${
                hecho ? 'bg-cuadra text-white' : actual ? 'bg-accent text-white' : 'bg-line text-ink-soft'
              }`}
            >
              {hecho ? <Check size={11} aria-hidden="true" /> : n}
            </span>
            <span className={`truncate ${actual ? 'font-semibold' : 'text-ink-soft'}`}>{t}</span>
            {n < PASOS.length && <span className="text-ink-soft" aria-hidden="true">→</span>}
          </li>
        )
      })}
    </ol>
  )
}
