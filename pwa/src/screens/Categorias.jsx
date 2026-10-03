import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Check, Eye, EyeOff, Plus, Trash2, X } from 'lucide-react'
import { api } from '../lib/api'
import { useCategorias } from '../lib/CategoriasContext'
import { useDialogos } from '../lib/DialogosContext'

const ICONOS_SUGERIDOS = ['🏷️', '🐾', '👶', '🎁', '✈️', '💻', '📚', '⚽', '🎨', '🛠️', '💅', '🧾']

export default function Categorias() {
  const navigate = useNavigate()
  const { categorias, cargando, recargar } = useCategorias()
  const [mostrarInactivas, setMostrarInactivas] = useState(false)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [editando, setEditando] = useState(null)

  async function toggleActiva(cat) {
    await api.editarCategoria(cat.id, { activa: !cat.activa })
    recargar()
  }

  const visibles = mostrarInactivas ? categorias : categorias.filter((c) => c.activa)

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pt-14 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="w-9 h-9 flex items-center justify-center -ml-2" aria-label="Volver">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-bold">Categorías</h1>
        </div>
        <button
          onClick={() => setMostrarForm(true)}
          className="w-9 h-9 rounded-full bg-accent text-white flex items-center justify-center"
         aria-label="Nueva categoría">
          <Plus size={18} />
        </button>
      </header>

      <p className="mx-6 mt-2 text-xs text-ink-soft">
        Crea las tuyas, cambia el ícono, o desactiva las que no uses — no te quedas pegado a
        las que trae la app por defecto.
      </p>

      <div className="mx-6 mt-4 flex items-center justify-between">
        <p className="text-xs text-ink-soft font-medium uppercase tracking-wide">
          {visibles.length} {visibles.length === 1 ? 'categoría' : 'categorías'}
        </p>
        <button
          onClick={() => setMostrarInactivas((v) => !v)}
          className="text-xs text-accent font-medium"
        >
          {mostrarInactivas ? 'Ocultar desactivadas' : 'Ver desactivadas'}
        </button>
      </div>

      {cargando ? (
        <p className="text-sm text-ink-soft text-center mt-8">Cargando...</p>
      ) : (
        <div className="mx-6 mt-3 rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
          {visibles.map((c) => (
            <div key={c.id} className={`flex items-center gap-3 px-4 py-3.5 ${!c.activa ? 'opacity-50' : ''}`}>
              <button
                onClick={() => setEditando(c)}
                className="flex items-center gap-3 flex-1 min-w-0 text-left"
              >
                <span className="text-xl shrink-0">{c.icono}</span>
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{c.nombre}</p>
                  {c.es_base && <p className="text-[11px] text-ink-soft">Categoría base</p>}
                </div>
              </button>
              <button
                onClick={() => toggleActiva(c)}
                className="w-9 h-9 shrink-0 flex items-center justify-center text-ink-soft"
                aria-label={c.activa ? 'Desactivar' : 'Activar'}
              >
                {c.activa ? <Eye size={16} /> : <EyeOff size={16} />}
              </button>
            </div>
          ))}
        </div>
      )}

      {mostrarForm && (
        <FormCategoria
          onClose={() => setMostrarForm(false)}
          onGuardada={() => {
            setMostrarForm(false)
            recargar()
          }}
        />
      )}

      {editando && (
        <FormCategoria
          categoria={editando}
          onClose={() => setEditando(null)}
          onGuardada={() => {
            setEditando(null)
            recargar()
          }}
          onEliminada={() => {
            setEditando(null)
            recargar()
          }}
        />
      )}
    </div>
  )
}

function FormCategoria({ categoria, onClose, onGuardada, onEliminada }) {
  const esEdicion = !!categoria
  const [nombre, setNombre] = useState(categoria?.nombre || '')
  const [icono, setIcono] = useState(categoria?.icono || ICONOS_SUGERIDOS[0])
  const [guardando, setGuardando] = useState(false)
  const [eliminando, setEliminando] = useState(false)
  const [error, setError] = useState('')
  const { confirmar } = useDialogos()

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a la categoría')

    setGuardando(true)
    try {
      if (esEdicion) {
        await api.editarCategoria(categoria.id, { nombre: nombre.trim(), icono })
      } else {
        await api.crearCategoria({ nombre: nombre.trim(), icono })
      }
      onGuardada()
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  async function eliminar() {
    const ok = await confirmar('Esto solo funciona si no tiene movimientos registrados.', {
      titulo: `¿Eliminar "${categoria.nombre}"?`,
      confirmarTexto: 'Eliminar',
      peligro: true,
    })
    if (!ok) return
    setEliminando(true)
    setError('')
    try {
      await api.eliminarCategoria(categoria.id)
      onEliminada()
    } catch (err) {
      setError(err.message || 'No se pudo eliminar')
      setEliminando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50 sheet-backdrop">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8 sheet-content">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{esEdicion ? 'Editar categoría' : 'Nueva categoría'}</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>

        <div className="flex gap-2 flex-wrap justify-center mb-5">
          {ICONOS_SUGERIDOS.map((ic) => (
            <button
              key={ic}
              onClick={() => setIcono(ic)}
              className={`w-11 h-11 rounded-2xl border-2 flex items-center justify-center text-lg ${
                icono === ic ? 'border-accent bg-accent-soft' : 'border-line'
              }`}
            >
              {ic}
            </button>
          ))}
        </div>

        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Nombre (ej. Mascotas)"
          maxLength={30}
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
        />

        {esEdicion && categoria.es_base && (
          <p className="text-xs text-ink-soft mb-4">
            Esta es una categoría base de la app — puedes cambiarle el nombre o el ícono, pero no
            eliminarla del todo.
          </p>
        )}

        {error && <p className="text-sm text-danger mb-3">{error}</p>}

        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60 flex items-center justify-center gap-2"
        >
          {guardando ? 'Guardando...' : (
            <>
              <Check size={16} /> {esEdicion ? 'Guardar cambios' : 'Crear categoría'}
            </>
          )}
        </button>

        {esEdicion && !categoria.es_base && (
          <button
            onClick={eliminar}
            disabled={eliminando}
            className="w-full flex items-center justify-center gap-1.5 mt-3 text-sm text-danger font-medium disabled:opacity-60"
          >
            <Trash2 size={14} /> {eliminando ? 'Eliminando...' : 'Eliminar categoría'}
          </button>
        )}
      </div>
    </div>
  )
}
