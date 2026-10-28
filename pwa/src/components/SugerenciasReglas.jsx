import { textoError } from '../lib/textoError'
import { useCallback, useEffect, useState } from 'react'
import { Sparkles, Undo2, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { plural } from '../lib/porCategorizar'

/**
 * Sugerencias de reglas: comercios que la persona ya categorizó igual 3 o más veces. Salen SIN marcar:
 * ninguna regla se crea sin que la elija. «Crear las seleccionadas» crea solo esas; «Descartar» hace que
 * la sugerencia no vuelva a salir (se puede deshacer en el momento).
 */
export default function SugerenciasReglas({ onCreadas }) {
  const [lista, setLista] = useState(null)
  const [marcadas, setMarcadas] = useState(new Set())
  const [aviso, setAviso] = useState(null)
  const [ocupado, setOcupado] = useState(false)

  const cargar = useCallback(async () => {
    try {
      const r = await api.sugerenciasReglas()
      setLista(r?.sugerencias || [])
    } catch {
      setLista([])
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  if (!lista || lista.length === 0) {
    return aviso ? (
      <p className="mx-6 mt-4 rounded-2xl bg-accent-soft px-4 py-3 text-sm" role="status">
        {aviso.texto}
      </p>
    ) : null
  }

  const alternar = (h) =>
    setMarcadas((s) => {
      const n = new Set(s)
      if (n.has(h)) n.delete(h)
      else n.add(h)
      return n
    })

  async function crear() {
    const elegidas = lista.filter((s) => marcadas.has(s.huella)).map((s) => ({ huella: s.huella, categoria: s.categoria }))
    if (!elegidas.length) return
    setOcupado(true)
    try {
      const r = await api.crearSugerencias(elegidas)
      setAviso({ texto: `Creé ${plural(r.creadas.length, 'regla', 'reglas')}.` })
      setMarcadas(new Set())
      await cargar()
      onCreadas?.()
    } catch (err) {
      setAviso({ texto: textoError(err, 'crear') })
    }
    setOcupado(false)
  }

  async function descartar(s) {
    setOcupado(true)
    try {
      await api.descartarSugerencias([s.huella])
      setAviso({ texto: `No te volveré a sugerir «${s.huella}».`, deshacer: [s.huella] })
      setMarcadas((m) => {
        const n = new Set(m)
        n.delete(s.huella)
        return n
      })
      await cargar()
    } catch (err) {
      setAviso({ texto: err.message || 'No se pudo descartar.' })
    }
    setOcupado(false)
  }

  async function deshacer() {
    await api.restaurarSugerencias(aviso.deshacer)
    setAviso(null)
    await cargar()
  }

  return (
    <section className="mx-6 mt-5" aria-label="Sugerencias de reglas">
      <h2 className="text-sm font-semibold flex items-center gap-2">
        <Sparkles size={16} className="text-accent" /> Reglas que te pueden servir ({lista.length})
      </h2>
      <p className="text-xs text-ink-soft mt-0.5 mb-2">
        Estos comercios ya los categorizaste igual varias veces. Marca los que quieras volver automáticos; no creo nada sin que lo elijas.
      </p>
      {aviso && (
        <p className="mb-2 rounded-2xl bg-accent-soft px-4 py-3 text-sm flex items-center gap-3" role="status">
          <span className="flex-1">{aviso.texto}</span>
          {aviso.deshacer && (
            <button onClick={deshacer} className="font-semibold underline flex items-center gap-1 min-h-[44px]">
              <Undo2 size={16} /> Deshacer
            </button>
          )}
        </p>
      )}
      <ul className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
        {lista.map((s) => (
          <li key={s.huella} className="flex items-center gap-3 px-4 py-3" data-testid="sugerencia-regla">
            <input
              type="checkbox"
              checked={marcadas.has(s.huella)}
              onChange={() => alternar(s.huella)}
              aria-label={`Crear regla: ${s.huella} es ${s.categoria}`}
              className="w-5 h-5 accent-[var(--c-accent)] shrink-0"
            />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium truncate capitalize">{s.huella}</p>
              <p className="text-xs text-ink-soft">
                → {s.categoria} · {plural(s.conteo, 'vez', 'veces')} · {formatCOP(s.monto_total)}
              </p>
            </div>
            <button
              onClick={() => descartar(s)}
              disabled={ocupado}
              aria-label={`Descartar la sugerencia de ${s.huella}`}
              className="w-11 h-11 -mr-2 flex items-center justify-center text-ink-soft shrink-0"
            >
              <X size={16} />
            </button>
          </li>
        ))}
      </ul>
      <button
        onClick={crear}
        disabled={ocupado || marcadas.size === 0}
        className="mt-3 w-full rounded-xl bg-ink text-paper px-4 py-3 text-sm font-semibold min-h-[44px] disabled:opacity-50"
      >
        Crear las seleccionadas{marcadas.size > 0 ? ` (${marcadas.size})` : ''}
      </button>
    </section>
  )
}
