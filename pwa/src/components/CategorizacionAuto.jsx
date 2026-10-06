import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, ChevronRight, X } from 'lucide-react'
import { api } from '../lib/api'
import { useCategorias } from '../lib/CategoriasContext'
import { patronDeComercio, RAZON_AUTO } from '../lib/comercio'

/** Insignia discreta que dice que la app puso la categoría sola, y por qué. */
export function InsigniaAuto({ movimiento }) {
  const razon = RAZON_AUTO[movimiento.cat_origen]
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] font-semibold leading-none px-1.5 py-1 rounded-full bg-accent-soft text-accent ml-1.5 align-middle"
      title={razon ? `Categoría puesta automáticamente ${razon}` : 'Categoría puesta automáticamente'}
    >
      Auto{razon ? ` · ${razon}` : ''}
    </span>
  )
}

/** Resumen tras importar: "Categoricé N movimientos: revísalos" -> vista Por revisar. */
export function AvisoCategorizados({ n, className = '' }) {
  if (!n || n < 1) return null
  return (
    <Link
      to="/movimientos?revisar=1"
      className={`flex items-center justify-between gap-3 rounded-2xl bg-accent-soft border border-accent/30 px-4 py-3 ${className}`}
    >
      <span className="text-sm text-ink">
        Categoricé <b>{n}</b> {n === 1 ? 'movimiento' : 'movimientos'} por mi cuenta:{' '}
        <span className="font-semibold text-accent">revísalos</span>
      </span>
      <ChevronRight size={16} className="text-accent shrink-0" />
    </Link>
  )
}

/**
 * Hoja para corregir la categoría de un movimiento. Si se marca "Aplicar a
 * todos los de este comercio" se crea una regla de categoría (visible en
 * Reglas de categorización) y se corrigen los movimientos que ya coinciden.
 */
export function HojaCambiarCategoria({ movimiento, onClose, onHecho }) {
  const { nombres, iconoDe } = useCategorias()
  const opciones = [...new Set([...nombres])].filter((n) => n !== 'Transferencias')
  const [categoria, setCategoria] = useState(
    opciones.includes(movimiento.categoria) && movimiento.categoria !== 'Otros' ? movimiento.categoria : ''
  )
  const [aplicarATodos, setAplicarATodos] = useState(true)
  const [patron, setPatron] = useState(patronDeComercio(movimiento.descripcion))
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    if (!categoria) return setError('Elige una categoría')
    if (aplicarATodos && !patron.trim()) return setError('Escribe el comercio al que aplicar la regla')
    setGuardando(true)
    setError('')
    try {
      const r = await api.recategorizarComercio(movimiento.id, {
        categoria,
        aplicar_a_todos: aplicarATodos,
        patron: aplicarATodos ? patron.trim() : null,
      })
      onHecho(r, categoria)
    } catch (err) {
      setError(err.message || 'No se pudo cambiar la categoría')
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50 sheet-backdrop">
      <div className="w-full max-w-[480px] max-h-[90vh] overflow-y-auto bg-paper rounded-t-[28px] p-6 pb-8 sheet-content">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold">Cambiar categoría</h2>
          <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>
        <p className="text-xs text-ink-soft mb-4 truncate">{movimiento.descripcion}</p>

        <div className="flex flex-wrap gap-2 mb-4" role="group" aria-label="Categorías">
          {opciones.map((n) => (
            <button
              key={n}
              type="button"
              aria-pressed={categoria === n}
              onClick={() => setCategoria(n)}
              className={`text-sm px-3 py-2 rounded-full border ${
                categoria === n ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
              }`}
            >
              <span aria-hidden="true">{iconoDe(n)}</span> {n}
            </button>
          ))}
        </div>

        <label className="flex items-start gap-3 rounded-2xl border border-line bg-paper-raised p-3 cursor-pointer">
          <input
            type="checkbox"
            checked={aplicarATodos}
            onChange={(e) => setAplicarATodos(e.target.checked)}
            className="mt-0.5 w-4 h-4 accent-[var(--c-accent)]"
          />
          <span className="text-sm">
            <span className="font-medium">Aplicar a todos los de este comercio</span>
            <span className="block text-xs text-ink-soft mt-0.5">
              Crea una regla: los movimientos que contengan este texto, de hoy y de los próximos, quedarán en esta categoría.
            </span>
          </span>
        </label>
        {aplicarATodos && (
          <input
            value={patron}
            onChange={(e) => setPatron(e.target.value)}
            aria-label="Comercio de la regla"
            maxLength={60}
            className="w-full mt-2 rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-sm outline-none focus:border-accent"
          />
        )}

        {error && <p className="text-sm text-danger mt-3">{error}</p>}

        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full mt-4 bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60 flex items-center justify-center gap-2"
        >
          <Check size={16} /> {guardando ? 'Guardando...' : 'Guardar'}
        </button>
      </div>
    </div>
  )
}
