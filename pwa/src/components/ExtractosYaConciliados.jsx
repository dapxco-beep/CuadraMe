import { useState } from 'react'
import { CheckCircle2, ChevronDown } from 'lucide-react'
import { BANCO_SIN_IDENTIFICAR, textoCruzados } from '../lib/sincronizacion'

/**
 * Sección plegada 'Extractos ya revisados (N)': extractos cuyo periodo ya quedó cruzado.
 * No molesta (cerrada por defecto, no cuenta como pendiente) pero se puede consultar:
 * banco, cuenta, periodo y cuántos movimientos se cruzaron. Si el usuario quiere,
 * puede "Revisar de nuevo" (vuelve a pasar el extracto por la conciliación).
 */
export default function ExtractosYaConciliados({ items, nombreCuenta = () => '', onVer, onRevisar, ocupados, abiertoInicial = false }) {
  const [abierto, setAbierto] = useState(abiertoInicial)
  if (!items || items.length === 0) return null
  return (
    <div className="mt-4" data-testid="ya-conciliados">
      <button
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className="w-full flex items-center justify-between text-sm font-semibold text-ink-soft py-2"
      >
        <span className="flex items-center gap-1.5">
          <CheckCircle2 size={16} className="text-cuadra" aria-hidden="true" /> Extractos ya revisados ({items.length})
        </span>
        <ChevronDown size={16} className={`shrink-0 transition-transform ${abierto ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      {abierto && (
        <ul className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
          {items.map((ex) => {
            const cuenta = nombreCuenta(ex.cuenta_sugerida_id)
            return (
              <li key={ex.id} className="px-4 py-3" data-testid={`conciliado-${ex.id}`}>
                <p className="text-sm font-medium truncate">
                  {ex.banco || BANCO_SIN_IDENTIFICAR}{ex.periodo ? ` · ${ex.periodo}` : ''}
                </p>
                <p className="text-xs text-ink-soft truncate">
                  {cuenta ? `${cuenta} · ` : ''}
                  {ex.cruzados != null ? textoCruzados(ex.cruzados) : 'Revisado'}
                </p>
                {(ex.historial_id && onVer) || (ex.estado === 'ya_conciliado' && cuenta && onRevisar) ? (
                  <div className="flex gap-3 mt-1.5">
                    {ex.historial_id && onVer && (
                      <button onClick={() => onVer(ex)} className="text-xs font-semibold text-accent">Ver qué se encontró</button>
                    )}
                    {ex.estado === 'ya_conciliado' && cuenta && onRevisar && (
                      <button
                        onClick={() => onRevisar(ex)}
                        disabled={ocupados?.has(ex.id)}
                        className="text-xs font-semibold text-ink-soft disabled:opacity-50"
                      >
                        {ocupados?.has(ex.id) ? 'Abriendo...' : 'Revisar de nuevo'}
                      </button>
                    )}
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
