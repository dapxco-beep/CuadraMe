import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { api } from '../lib/api'
import { useCategorias } from '../lib/CategoriasContext'
import { formatCOP } from '../lib/format'

/**
 * «Ver por subcategoría»: desglose de UNA categoría en el periodo (incluye «Sin subcategoría»).
 * Solo aparece si la categoría tiene subcategorías. La cifra de la categoría no cambia: esto solo detalla.
 */
export default function DesgloseSubcategorias({ categoria, params = { periodo: 'este_mes' } }) {
  const { subsDe } = useCategorias()
  const [abierto, setAbierto] = useState(false)
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(false)

  if (!subsDe || subsDe(categoria).length === 0) return null

  function alternar() {
    const siguiente = !abierto
    setAbierto(siguiente)
    if (siguiente && !datos) {
      Promise.resolve(api.desgloseSubcategorias?.(categoria, params))
        .then((d) => setDatos(d))
        .catch(() => setError(true))
    }
  }

  return (
    <div className="mt-1 mb-2">
      <button
        type="button"
        onClick={alternar}
        aria-expanded={abierto}
        className="flex items-center gap-1 text-xs font-semibold text-ink-soft min-h-[32px]"
      >
        Ver por subcategoría
        <ChevronDown size={16} className={abierto ? 'rotate-180' : ''} aria-hidden="true" />
      </button>
      {abierto && error && <p className="text-xs text-danger">No se pudo cargar el desglose.</p>}
      {abierto && !datos && !error && <p className="text-xs text-ink-soft">Cargando...</p>}
      {abierto && datos && (
        <ul className="mt-1 rounded-xl bg-paper border border-line divide-y divide-line" aria-label={`Subcategorías de ${categoria}`}>
          {datos.subcategorias.map((s) => (
            <li key={s.subcategoria || '__sin'} className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
              <span className="min-w-0 truncate">{s.subcategoria || 'Sin subcategoría'}</span>
              <span className="shrink-0">
                <span className="font-semibold">{formatCOP(s.total)}</span>
                <span className="text-ink-soft"> · {s.porcentaje} %</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
