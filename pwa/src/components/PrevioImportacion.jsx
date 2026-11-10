import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Pencil, Plus } from 'lucide-react'
import { formatCOP } from '../lib/format'
import { resumenPrevio, textoCorrecciones, textoPrevio } from '../lib/subidaMultiple'
import { esMismoGastoSeguro } from '../lib/modoAutomatico'
import { iniciar as iniciarAutoarreglo } from '../lib/autoarreglo'

// «Esto es lo que va a pasar»: antes de traer nada, cuántas líneas ya las tienes, cuántas son nuevas y
// cuáles parecen repetidas. Las dudosas se muestran en dos filas lado a lado: «¿es el mismo gasto?».
// `onDecidir(items, 'mismo' | 'otro', auto)` resuelve una o varias a la vez (en bloque).
// Modo automático (`automatico`): si el monto es idéntico, hay ≤ 3 días y es 1:1, NO se pregunta: se junta solo
// (`servidor`: el extracto ya está en el servidor y el autoarreglo lo junta con «Deshacer»; si no, se junta aquí y
// `onDeshacerAuto` lo separa). Solo se pregunta cuando el monto difiere o hay dudas.
export default function PrevioImportacion({ items, onDecidir, onDeshacerAuto, automatico = false, servidor = false, className = '' }) {
  const todasDudosas = items.filter((i) => i.estado === 'dudoso')
  const seguras = automatico ? todasDudosas.filter((i) => esMismoGastoSeguro(i, todasDudosas)) : []
  const dudosas = todasDudosas.filter((i) => !seguras.includes(i))
  const unidas = items.filter((i) => i.autoUnida)
  const r = resumenPrevio(servidor ? items.filter((i) => !seguras.includes(i)) : items)
  const [ocupado, setOcupado] = useState(false)
  const yaIntentado = useRef('')
  async function decidir(lista, decision, auto = false) {
    setOcupado(true)
    try {
      await onDecidir(lista, decision, auto)
    } finally {
      setOcupado(false)
    }
  }
  const clave = seguras.map((i) => i.k).join('|')
  useEffect(() => {
    if (!clave || yaIntentado.current === clave) return
    yaIntentado.current = clave
    if (servidor) iniciarAutoarreglo({ forzar: true })
    else decidir(seguras, 'mismo', true).catch(() => {}) // si falla, quedan como dudosas y se preguntan
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, servidor])
  const [coincide, nuevo, dudoso] = textoPrevio(r)
  return (
    <section className={`rounded-2xl border border-line bg-paper-raised p-3.5 ${className}`} aria-label="Esto es lo que va a pasar" data-testid="previo-importacion">
      <h4 className="text-sm font-semibold">Esto es lo que va a pasar</h4>
      <ul className="mt-2 space-y-1.5 text-xs">
        <li className="flex items-start gap-1.5"><CheckCircle2 size={16} className="text-cuadra shrink-0" aria-hidden="true" /> {coincide}</li>
        <li className="flex items-start gap-1.5"><Plus size={16} className="text-accent shrink-0" aria-hidden="true" /> {nuevo}</li>
        {r.correcciones > 0 && (
          <li className="flex items-start gap-1.5" data-testid="previo-correcciones"><Pencil size={16} className="text-accent shrink-0" aria-hidden="true" /> {textoCorrecciones(r.correcciones)}</li>
        )}
        {r.dudosos > 0 && (
          <li className="flex items-start gap-1.5 font-medium"><AlertTriangle size={16} className="text-accent shrink-0" aria-hidden="true" /> {dudoso}</li>
        )}
      </ul>
      {(servidor ? seguras : unidas).length > 0 && (
        <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-medium text-accent" role="status" data-testid="previo-unidas">
          <CheckCircle2 size={16} className="shrink-0" aria-hidden="true" />
          <span>
            {(servidor ? seguras : unidas).length === 1
              ? (servidor ? '1 línea es el mismo gasto que ya tenías (mismo monto y fecha): la junto yo.' : 'Junté 1 línea que era el mismo gasto (mismo monto y fecha).')
              : `${(servidor ? seguras : unidas).length} líneas ${servidor ? 'son' : 'eran'} el mismo gasto que ya tenías (mismo monto y fecha): ${servidor ? 'las junto yo' : 'las junté'}.`}
          </span>
          {!servidor && onDeshacerAuto && (
            <button type="button" disabled={ocupado} onClick={() => onDeshacerAuto(unidas)} className="min-h-[44px] rounded-xl px-3 text-xs font-semibold underline disabled:opacity-60" data-testid="previo-deshacer-union">
              Deshacer
            </button>
          )}
        </p>
      )}
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
