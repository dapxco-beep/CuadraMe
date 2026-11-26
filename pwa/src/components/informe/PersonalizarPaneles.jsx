import { useState } from 'react'
import { ArrowDown, ArrowUp, Eye, EyeOff, SlidersHorizontal } from 'lucide-react'
import { PANELES } from '../../lib/panelesInforme'

/** «Personalizar»: elegir qué paneles se ven en Informes y en qué orden. Se guarda solo en este dispositivo. */
export default function PersonalizarPaneles({ paneles, lista = PANELES, className = '' }) {
  const [abierto, setAbierto] = useState(false)
  const nombre = (id) => lista.find((p) => p.id === id)?.nombre || id
  return (
    <section className={className}>
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className="inline-flex items-center gap-1.5 min-h-11 px-3 rounded-full border border-line bg-paper-raised text-xs font-semibold text-accent"
      >
        <SlidersHorizontal size={16} aria-hidden="true" />
        {abierto ? 'Listo' : 'Personalizar paneles'}
      </button>
      {abierto && (
        <div className="mt-2 rounded-2xl border border-line bg-paper-raised p-3" data-testid="personalizar-paneles">
          <p className="text-xs text-ink-soft">Muestra solo lo que usas y ponlo en el orden que quieras. Se guarda en este celular.</p>
          <ul className="mt-2 divide-y divide-line">
            {paneles.orden.map((id, i) => {
              const visible = paneles.visible(id)
              return (
                <li key={id} className="flex items-center gap-1 py-1">
                  <button
                    type="button"
                    onClick={() => paneles.alternar(id)}
                    aria-pressed={visible}
                    aria-label={`${visible ? 'Ocultar' : 'Mostrar'} ${nombre(id)}`}
                    className="min-h-11 min-w-11 flex items-center justify-center text-ink-soft"
                  >
                    {visible ? <Eye size={18} aria-hidden="true" /> : <EyeOff size={18} aria-hidden="true" />}
                  </button>
                  <span className={`flex-1 text-sm ${visible ? '' : 'text-ink-soft line-through'}`}>{nombre(id)}</span>
                  <button type="button" onClick={() => paneles.mover(id, -1)} disabled={i === 0} aria-label={`Subir ${nombre(id)}`} className="min-h-11 min-w-11 flex items-center justify-center disabled:opacity-30">
                    <ArrowUp size={16} aria-hidden="true" />
                  </button>
                  <button type="button" onClick={() => paneles.mover(id, 1)} disabled={i === paneles.orden.length - 1} aria-label={`Bajar ${nombre(id)}`} className="min-h-11 min-w-11 flex items-center justify-center disabled:opacity-30">
                    <ArrowDown size={16} aria-hidden="true" />
                  </button>
                </li>
              )
            })}
          </ul>
          <button type="button" onClick={paneles.restaurar} className="mt-1 min-h-11 text-xs font-semibold text-accent">
            Volver al orden original
          </button>
        </div>
      )}
    </section>
  )
}
