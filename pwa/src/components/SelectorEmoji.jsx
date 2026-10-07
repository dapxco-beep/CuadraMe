import { useState } from 'react'
import { Search } from 'lucide-react'
import { GRUPOS_EMOJI, buscarEmojis, esEmoji, primerGrafema } from '../lib/emojis'

/**
 * Selector de emoji sin dependencias: un campo donde se puede pegar o escribir
 * con el teclado emoji del teléfono (acepta CUALQUIER emoji) más una cuadrícula
 * por grupos con búsqueda para quien prefiere elegir.
 */
export default function SelectorEmoji({ valor, onChange }) {
  const [grupoId, setGrupoId] = useState(GRUPOS_EMOJI[0].id)
  const [busqueda, setBusqueda] = useState('')
  const [aviso, setAviso] = useState('')

  const grupo = GRUPOS_EMOJI.find((g) => g.id === grupoId) || GRUPOS_EMOJI[0]
  const resultados = busqueda.trim() ? buscarEmojis(busqueda) : null
  const lista = resultados ?? grupo.items.map(([e]) => e)

  function alEscribir(texto) {
    if (!texto) {
      setAviso('')
      return
    }
    // Se queda con el último emoji escrito: así reemplazarlo es solo teclear otro.
    const ultimo = primerGrafema(texto)
    if (esEmoji(ultimo)) {
      setAviso('')
      onChange(ultimo)
    } else {
      setAviso('Solo se aceptan emojis. Usa el teclado de emojis de tu teléfono o elige uno abajo.')
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <span
          className="w-14 h-14 rounded-2xl bg-accent-soft border-2 border-accent flex items-center justify-center text-3xl shrink-0"
          aria-label="Emoji elegido"
          role="img"
        >
          {valor}
        </span>
        <div className="flex-1 min-w-0">
          <input
            value=""
            onChange={(e) => alEscribir(e.target.value)}
            aria-label="Escribir un emoji con el teclado"
            placeholder="Toca y usa el teclado de emojis 😀"
            className="w-full rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-sm outline-none focus:border-accent"
          />
          {aviso && <p className="text-[11px] text-danger mt-1">{aviso}</p>}
        </div>
      </div>

      <div className="flex items-center gap-2 bg-paper-raised border border-line rounded-xl px-3 py-2 mb-2">
        <Search size={16} className="text-ink-soft" />
        <input
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          aria-label="Buscar emoji"
          placeholder="Buscar: perro, café, gimnasio…"
          className="bg-transparent outline-none text-sm flex-1 placeholder:text-ink-soft"
        />
      </div>

      {!resultados && (
        <div className="flex gap-1.5 overflow-x-auto no-scrollbar mb-2" role="tablist" aria-label="Grupos de emojis">
          {GRUPOS_EMOJI.map((g) => (
            <button
              key={g.id}
              role="tab"
              aria-selected={g.id === grupoId}
              aria-label={g.titulo}
              onClick={() => setGrupoId(g.id)}
              className={`shrink-0 w-9 h-9 rounded-xl flex items-center justify-center text-lg border ${
                g.id === grupoId ? 'border-accent bg-accent-soft' : 'border-line'
              }`}
            >
              {g.icono}
            </button>
          ))}
        </div>
      )}

      <div className="max-h-44 overflow-y-auto rounded-xl border border-line p-1.5">
        {lista.length === 0 ? (
          <p className="text-xs text-ink-soft text-center py-4">
            No hay emojis con ese nombre. Prueba con otra palabra o escríbelo con el teclado.
          </p>
        ) : (
          <div className="grid grid-cols-7 gap-1">
            {lista.map((e) => (
              <button
                key={e}
                type="button"
                aria-label={`Elegir ${e}`}
                onClick={() => {
                  setAviso('')
                  onChange(e)
                }}
                className={`h-10 rounded-lg flex items-center justify-center text-xl ${
                  valor === e ? 'bg-accent-soft ring-2 ring-accent' : 'hover:bg-paper-raised'
                }`}
              >
                {e}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
