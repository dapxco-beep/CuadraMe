import { useState } from 'react'
import { Pencil } from 'lucide-react'
import { limpiarNombre, MAX_NOMBRE } from '../lib/tituloMovimiento'

// Lápiz pequeño que abre la edición del nombre. Área táctil de 44 px sin hacer la fila más alta.
export function BotonLapiz({ original, onClick, className = '' }) {
  return (
    <button
      type="button"
      aria-label={`Cambiar nombre de ${original}`}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        onClick(e)
      }}
      className={`relative shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-md text-ink-soft hover:text-accent before:absolute before:-inset-2.5 before:content-[''] ${className}`}
    >
      <Pencil size={16} aria-hidden="true" />
    </button>
  )
}

/** «Banco: …» en pequeño: el texto original, para no perder de vista de dónde viene. */
export function PistaBanco({ original, className = '' }) {
  return (
    <p className={`text-[11px] text-ink-soft break-words line-clamp-2 ${className}`} data-testid="pista-banco">
      Banco: {original}
    </p>
  )
}

/**
 * Editor del nombre: un campo con el texto del banco como pista (placeholder).
 * Guardar con el campo vacío = volver al original. `conRecordar` agrega la casilla
 * «Recordar este nombre para este comercio» (apagada salvo que el comercio se repita mucho).
 */
export function EditorNombre({ original, valor = '', recordarInicial = false, conRecordar = false, onGuardar, onCancelar, guardando = false, className = '' }) {
  const [texto, setTexto] = useState(valor || '')
  const [recordar, setRecordar] = useState(!!recordarInicial)
  const limpio = limpiarNombre(texto)
  const guardar = () => onGuardar(limpio, conRecordar ? recordar : false)
  return (
    <div className={className} data-testid="editor-nombre">
      <input
        type="text"
        autoFocus
        value={texto}
        maxLength={MAX_NOMBRE}
        placeholder={original}
        aria-label={`Nombre de ${original}`}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            guardar()
          } else if (e.key === 'Escape') {
            e.stopPropagation()
            onCancelar()
          }
        }}
        className="w-full rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm outline-none focus:border-accent"
      />
      <p className="text-[11px] text-ink-soft mt-1">Solo cambia cómo lo ves tú. Lo que dice el banco se conserva.</p>
      {conRecordar && limpio && (
        <label className="flex items-center gap-2 text-xs text-ink mt-2">
          <input type="checkbox" checked={recordar} onChange={(e) => setRecordar(e.target.checked)} className="w-4 h-4 accent-accent shrink-0" />
          <span>Recordar este nombre para este comercio</span>
        </label>
      )}
      <div className="flex flex-wrap gap-2 mt-2">
        <button type="button" onClick={guardar} disabled={guardando} className="min-h-[44px] px-4 rounded-xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-60">
          Guardar
        </button>
        <button type="button" onClick={onCancelar} className="min-h-[44px] px-4 rounded-xl border border-line text-sm text-ink-soft">
          Cancelar
        </button>
        {valor && (
          <button type="button" onClick={() => onGuardar('', false)} disabled={guardando} className="min-h-[44px] px-2 text-sm font-semibold text-accent">
            Volver al original
          </button>
        )}
      </div>
    </div>
  )
}
