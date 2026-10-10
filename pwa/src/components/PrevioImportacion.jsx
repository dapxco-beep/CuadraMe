import { useState } from 'react'
import { AlertTriangle, CheckCircle2, Plus } from 'lucide-react'
import { formatCOP } from '../lib/format'
import { resumenPrevio, textoPrevio } from '../lib/subidaMultiple'

// «Esto es lo que va a pasar»: antes de traer nada, cuántas líneas ya las tienes, cuántas son nuevas y
// cuáles parecen repetidas. Las dudosas se muestran en dos filas lado a lado: «¿es el mismo gasto?».
// `onDecidir(items, 'mismo' | 'otro')` resuelve una o varias a la vez (en bloque).
export default function PrevioImportacion({ items, onDecidir, className = '' }) {
  const r = resumenPrevio(items)
  const dudosas = items.filter((i) => i.estado === 'dudoso')
  const [ocupado, setOcupado] = useState(false)
  async function decidir(lista, decision) {
    setOcupado(true)
    try {
      await onDecidir(lista, decision)
    } finally {
      setOcupado(false)
    }
  }
  const [coincide, nuevo, dudoso] = textoPrevio(r)
  return (
    <section className={`rounded-2xl border border-line bg-paper-raised p-3.5 ${className}`} aria-label="Esto es lo que va a pasar" data-testid="previo-importacion">
      <h4 className="text-sm font-semibold">Esto es lo que va a pasar</h4>
      <ul className="mt-2 space-y-1.5 text-xs">
        <li className="flex items-start gap-1.5"><CheckCircle2 size={16} className="text-cuadra shrink-0" aria-hidden="true" /> {coincide}</li>
        <li className="flex items-start gap-1.5"><Plus size={16} className="text-accent shrink-0" aria-hidden="true" /> {nuevo}</li>
        {r.dudosos > 0 && (
          <li className="flex items-start gap-1.5 font-medium"><AlertTriangle size={16} className="text-accent shrink-0" aria-hidden="true" /> {dudoso}</li>
        )}
      </ul>
      {dudosas.length > 0 && (
        <div className="mt-3" data-testid="dudosas">
          {dudosas.length > 1 && (
            <div className="flex gap-2 mb-2">
              <button disabled={ocupado} onClick={() => decidir(dudosas, 'mismo')} className="flex-1 min-h-[44px] rounded-xl border border-line text-xs font-semibold disabled:opacity-60">
                Todos son el mismo gasto
              </button>
              <button disabled={ocupado} onClick={() => decidir(dudosas, 'otro')} className="flex-1 min-h-[44px] rounded-xl border border-line text-xs font-semibold disabled:opacity-60">
                Todos son otros
              </button>
            </div>
          )}
          {dudosas.map((it) => (
            <div key={`${it.k}`} className="rounded-xl bg-paper border border-line p-3 mb-2" data-testid={`dudosa-${it.k}`}>
              <p className="text-xs font-semibold mb-2">¿Es el mismo gasto?</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-paper-raised p-2">
                  <p className="text-ink-soft">En tu archivo</p>
                  <p className="font-medium break-words line-clamp-2">{it.descripcion}</p>
                  <p>{it.fecha} · {formatCOP(it.monto)}</p>
                </div>
                <div className="rounded-lg bg-paper-raised p-2">
                  <p className="text-ink-soft">Ya lo tenías</p>
                  <p className="font-medium break-words line-clamp-2">{it.registrado?.descripcion}</p>
                  <p>{it.registrado?.fecha} · {formatCOP(it.registrado?.monto)}</p>
                </div>
              </div>
              <div className="flex gap-2 mt-2">
                <button disabled={ocupado} onClick={() => decidir([it], 'mismo')} className="flex-1 min-h-[44px] rounded-xl bg-accent text-paper-raised text-xs font-semibold disabled:opacity-60">
                  Sí, es el mismo
                </button>
                <button disabled={ocupado} onClick={() => decidir([it], 'otro')} className="flex-1 min-h-[44px] rounded-xl border border-line text-xs font-semibold disabled:opacity-60">
                  No, es otro
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
