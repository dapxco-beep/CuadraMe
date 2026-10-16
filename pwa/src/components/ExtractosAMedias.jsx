import { FileClock } from 'lucide-react'
import { textoFaltan, tituloAMedias } from '../lib/retomar'

/**
 * «Tienes N extractos a medio conciliar»: cada extracto que quedó con movimientos por importar,
 * con su cuenta, su mes y un botón «Seguir» que abre EXACTAMENTE esa revisión.
 * `compacto` = el aviso discreto de Inicio (una línea con un solo botón).
 */
export default function ExtractosAMedias({ lista = [], onSeguir, compacto = false, className = '' }) {
  if (!lista.length) return null
  if (compacto) {
    return (
      <button
        type="button"
        onClick={() => onSeguir(lista[0])}
        data-testid="aviso-a-medias"
        className={`w-full flex items-center gap-2 rounded-2xl border border-line bg-paper px-4 py-3 text-left min-h-[44px] ${className}`}
      >
        <FileClock size={16} className="shrink-0 text-accent" aria-hidden="true" />
        <span className="flex-1 text-xs font-medium">{tituloAMedias(lista.length)}</span>
        <span className="text-xs font-semibold text-accent">Seguir</span>
      </button>
    )
  }
  return (
    <section className={`rounded-2xl border border-accent bg-accent-soft p-4 ${className}`} aria-label="Extractos a medio conciliar" data-testid="extractos-a-medias">
      <h2 className="text-sm font-semibold flex items-center gap-2">
        <FileClock size={16} aria-hidden="true" /> {tituloAMedias(lista.length)}
      </h2>
      <ul className="mt-2 divide-y divide-line">
        {lista.map((x) => (
          <li key={x.historialId} className="flex items-center gap-3 py-2">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium truncate">{x.cuenta}{x.mes ? ` · ${x.mes}` : ''}</p>
              <p className="text-xs text-ink-soft">{textoFaltan(x.faltan)}</p>
            </div>
            <button
              type="button"
              onClick={() => onSeguir(x)}
              aria-label={`Seguir con ${x.cuenta}${x.mes ? ` ${x.mes}` : ''}`}
              className="shrink-0 min-h-[44px] rounded-xl bg-ink text-paper text-sm font-semibold px-4"
            >
              Seguir
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
