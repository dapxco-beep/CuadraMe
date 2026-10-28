import { textoError } from '../lib/textoError'
import { useState } from 'react'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import { api } from '../lib/api'
import { useCategorias } from '../lib/CategoriasContext'
import { useDialogos } from '../lib/DialogosContext'

/**
 * Subcategorías de UNA categoría (pantalla Categorías, al abrir la categoría): lista, «+ Agregar
 * subcategoría» (nombre y un toque), renombrar y borrar. Son opcionales: la categoría sigue siendo la
 * que suma en informes y presupuestos; la subcategoría solo detalla (docs/SUBCATEGORIAS.md).
 */
export default function SubcategoriasDeCategoria({ categoria }) {
  const { subsDe, recargar } = useCategorias()
  const { confirmar, avisar } = useDialogos()
  const subs = subsDe ? subsDe(categoria.nombre) : []
  const [agregando, setAgregando] = useState(false)
  const [nombre, setNombre] = useState('')
  const [editandoId, setEditandoId] = useState(null)
  const [texto, setTexto] = useState('')
  const [ocupado, setOcupado] = useState(false)

  async function agregar() {
    const n = nombre.trim()
    if (!n) return avisar('Escribe el nombre de la subcategoría')
    setOcupado(true)
    try {
      await api.crearSubcategoria(categoria.nombre, n)
      setNombre('')
      setAgregando(false)
      await recargar()
    } catch (err) {
      avisar(textoError(err, 'crear la subcategoría'))
    } finally {
      setOcupado(false)
    }
  }

  async function renombrar(s) {
    const n = texto.trim()
    if (!n || n === s.nombre) {
      setEditandoId(null)
      return
    }
    setOcupado(true)
    try {
      await api.editarSubcategoria(s.id, n)
      setEditandoId(null)
      await recargar()
    } catch (err) {
      avisar(textoError(err, 'cambiar el nombre'))
    } finally {
      setOcupado(false)
    }
  }

  async function borrar(s) {
    const aviso = s.movimientos
      ? `«${s.nombre}» se quita de ${s.movimientos} ${s.movimientos === 1 ? 'movimiento' : 'movimientos'}. Siguen en ${categoria.nombre}.`
      : `Se borra «${s.nombre}».`
    const ok = await confirmar(aviso, { confirmarTexto: 'Borrar subcategoría' })
    if (!ok) return
    try {
      await api.eliminarSubcategoria(s.id)
      await recargar()
    } catch (err) {
      avisar(textoError(err, 'borrar'))
    }
  }

  return (
    <div className="bg-paper px-4 pb-3 pt-1 pl-[3.75rem]" data-testid={`subcategorias-${categoria.nombre}`}>
      {subs.length === 0 && !agregando && (
        <p className="text-xs text-ink-soft py-1.5">
          Sin subcategorías. Ej: {categoria.nombre} → una más específica.
        </p>
      )}
      <ul>
        {subs.map((s) => (
          <li key={s.id} className="flex items-center gap-1 min-h-[44px]">
            {editandoId === s.id ? (
              <>
                <input
                  value={texto}
                  onChange={(e) => setTexto(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && renombrar(s)}
                  aria-label={`Nuevo nombre de ${s.nombre}`}
                  maxLength={40}
                  autoFocus
                  className="flex-1 min-w-0 bg-paper-raised border border-line rounded-xl px-3 py-2 text-sm outline-none"
                />
                <button onClick={() => renombrar(s)} disabled={ocupado} className="w-11 h-11 flex items-center justify-center text-accent" aria-label="Guardar nombre">
                  <Check size={16} />
                </button>
                <button onClick={() => setEditandoId(null)} className="w-11 h-11 flex items-center justify-center text-ink-soft" aria-label="Cancelar">
                  <X size={16} />
                </button>
              </>
            ) : (
              <>
                <span className="flex-1 min-w-0 text-sm truncate">
                  {s.nombre}
                  <span className="text-[11px] text-ink-soft"> · {s.movimientos || 0} mov.</span>
                </span>
                <button
                  onClick={() => {
                    setEditandoId(s.id)
                    setTexto(s.nombre)
                  }}
                  className="w-11 h-11 flex items-center justify-center text-ink-soft"
                  aria-label={`Editar subcategoría ${s.nombre}`}
                >
                  <Pencil size={16} />
                </button>
                <button onClick={() => borrar(s)} className="w-11 h-11 flex items-center justify-center text-ink-soft" aria-label={`Borrar subcategoría ${s.nombre}`}>
                  <Trash2 size={16} />
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
      {agregando ? (
        <div className="flex items-center gap-2 mt-1">
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && agregar()}
            aria-label="Nombre de la subcategoría"
            placeholder="Ej: Gasolina"
            maxLength={40}
            autoFocus
            className="flex-1 min-w-0 bg-paper-raised border border-line rounded-xl px-3 py-2.5 text-sm outline-none"
          />
          <button
            onClick={agregar}
            disabled={ocupado}
            className="rounded-xl bg-ink text-paper text-sm font-semibold px-4 min-h-[44px] disabled:opacity-60"
          >
            Guardar
          </button>
        </div>
      ) : (
        <button
          onClick={() => setAgregando(true)}
          className="mt-1 flex items-center gap-1.5 text-sm font-semibold text-accent min-h-[44px]"
        >
          <Plus size={16} /> Agregar subcategoría
        </button>
      )}
    </div>
  )
}
