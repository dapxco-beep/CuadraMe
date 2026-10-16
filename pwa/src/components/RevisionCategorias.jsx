import { useState } from 'react'
import { CheckCircle2, CircleHelp, Sparkles, Tag } from 'lucide-react'
import { EMOJI_DEFECTO, EMOJI_SIN_CATEGORIA, ESTADOS_CATEGORIA, textoResumenCategorias } from '../lib/estadoCategoria'
import { opcionesCategoria } from '../lib/importar'
import HojaNuevaCategoria, { OPCION_NUEVA_CATEGORIA, TEXTO_NUEVA_CATEGORIA } from './HojaNuevaCategoria'

// Piezas de la revisión de un extracto o archivo: cómo quedó cada categoría (con su emoji, el mismo
// de Movimientos), el resumen de arriba y la acción en bloque. Todas son presentacionales: la
// pantalla decide qué hacer con lo que el usuario toque.

const ICONO_ESTADO = { auto: Sparkles, confirmada: CheckCircle2, revisar: CircleHelp, sin_categoria: Tag }

/** «🍔 Comida · Categorizado automáticamente». El estado nunca va solo en color: lleva ícono y texto. */
export function ChipCategoria({ categoria, emoji, estado, className = '' }) {
  const e = ESTADOS_CATEGORIA[estado] || ESTADOS_CATEGORIA.sin_categoria
  const Icono = ICONO_ESTADO[estado] || Tag
  const sin = estado === 'sin_categoria'
  return (
    <div className={`flex flex-wrap items-center gap-x-2 gap-y-1 ${className}`} data-testid="chip-categoria" data-estado={estado}>
      <span className="inline-flex items-center gap-1.5 text-xs font-semibold min-w-0 max-w-full">
        <span aria-hidden="true">{sin ? EMOJI_SIN_CATEGORIA : emoji || EMOJI_DEFECTO}</span>
        <span className="truncate">{sin ? 'Sin categoría' : categoria}</span>
      </span>
      <span className={`inline-flex items-center gap-1 text-[11px] font-medium rounded-full px-2 py-0.5 ${e.clase}`}>
        <Icono size={16} aria-hidden="true" className="shrink-0" />
        {e.texto}
      </span>
    </div>
  )
}

/** Resumen de arriba: «37 categorizados, 5 por revisar». Con atajos para marcar lo que falta. */
export function ResumenCategorias({ resumen, onMarcar, className = '' }) {
  if (!resumen || resumen.total === 0) return null
  return (
    <div className={`rounded-2xl bg-paper border border-line px-4 py-3 ${className}`} data-testid="resumen-categorias">
      <p className="text-sm font-semibold" role="status">{textoResumenCategorias(resumen)}</p>
      {(resumen.revisar > 0 || resumen.sin_categoria > 0) && onMarcar && (
        <div className="flex flex-wrap gap-2 mt-2">
          {resumen.revisar > 0 && (
            <button
              type="button"
              onClick={() => onMarcar('revisar')}
              className="min-h-[44px] rounded-xl border border-line px-3 text-xs font-semibold"
            >
              Marcar las {resumen.revisar} por revisar
            </button>
          )}
          {resumen.sin_categoria > 0 && (
            <button
              type="button"
              onClick={() => onMarcar('sin_categoria')}
              className="min-h-[44px] rounded-xl border border-line px-3 text-xs font-semibold"
            >
              Marcar las {resumen.sin_categoria} sin categoría
            </button>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Acción en bloque: pone UNA categoría a todas las líneas marcadas y, si se deja la casilla,
 * recuerda la regla de cada comercio (el mismo aprendizaje de siempre: una regla por comercio).
 * onAplicar(categoria, recordar) lo resuelve la pantalla.
 */
export function CategoriaEnBloque({ cantidad, nombres, iconoDe, onAplicar, aviso = '', className = '' }) {
  const [categoria, setCategoria] = useState('')
  const [recordar, setRecordar] = useState(true)
  const [creando, setCreando] = useState(false)
  if (!cantidad) return null
  return (
    <div className={`rounded-2xl bg-paper border border-line p-4 ${className}`} data-testid="categoria-en-bloque">
      <p className="text-sm font-semibold">
        Poner una categoría a las {cantidad} {cantidad === 1 ? 'marcada' : 'marcadas'}
      </p>
      <label className="block mt-2">
        <span className="sr-only">Categoría para las marcadas</span>
        <select
          value={categoria}
          onChange={(e) => (e.target.value === OPCION_NUEVA_CATEGORIA ? setCreando(true) : setCategoria(e.target.value))}
          className="w-full rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-xs"
        >
          <option value="">Elige la categoría</option>
          {opcionesCategoria(nombres, '').map((n) => (
            <option key={n} value={n}>{iconoDe(n)} {n}</option>
          ))}
          <option value={OPCION_NUEVA_CATEGORIA}>{TEXTO_NUEVA_CATEGORIA}</option>
        </select>
      </label>
      {creando && <HojaNuevaCategoria onCerrar={() => setCreando(false)} onCreada={(n) => setCategoria(n)} />}
      <label className="flex items-center gap-2 mt-2 text-xs min-h-[44px]">
        <input
          type="checkbox"
          checked={recordar}
          onChange={(e) => setRecordar(e.target.checked)}
          className="w-4 h-4 accent-accent shrink-0"
        />
        <span>Recordar esta regla para cada comercio</span>
      </label>
      {aviso && <p className="text-[11px] text-ink-soft -mt-1 mb-2">{aviso}</p>}
      <button
        type="button"
        disabled={!categoria}
        onClick={() => {
          onAplicar(categoria, recordar)
          setCategoria('')
        }}
        className="w-full min-h-[44px] rounded-xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-50"
      >
        Aplicar a las {cantidad}
      </button>
    </div>
  )
}
