import { useEffect, useState } from 'react'
import { EstadoVacio } from '../brand/Marca'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Plus, Trash2, X, Tag } from 'lucide-react'
import { api } from '../lib/api'
import { useCategorias } from '../lib/CategoriasContext'
import Hoja from '../components/Hoja'

export default function ReglasCategoria() {
  const volver = useVolver('/perfil')
  const [reglas, setReglas] = useState([])
  const [cargando, setCargando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    cargar()
  }, [])

  async function cargar() {
    setCargando(true)
    setError('')
    try {
      setReglas(await api.reglasCategoria())
    } catch (err) {
      setError(err.message || 'No se pudieron cargar tus reglas')
    }
    setCargando(false)
  }

  async function eliminar(id) {
    await api.eliminarReglaCategoria(id)
    cargar()
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-bold">Reglas de categorización</h1>
        </div>
        <button
          onClick={() => setMostrarForm(true)}
          className="w-11 h-11 rounded-full bg-accent text-white flex items-center justify-center"
         aria-label="Nueva regla">
          <Plus size={18} />
        </button>
      </header>

      <p className="mx-6 mt-2 text-xs text-ink-soft">
        Cuando un movimiento contenga este texto, se categoriza automáticamente al instante.
        Tienen prioridad sobre la categorización que aprende de tu historial.
      </p>

      {cargando ? (
        <p className="text-sm text-ink-soft text-center mt-8">Cargando...</p>
      ) : error ? (
        <div className="mx-6 mt-6 rounded-2xl bg-danger-soft p-6 text-center">
          <p className="text-sm text-danger mb-3">{error}</p>
          <button onClick={cargar} className="text-sm font-semibold text-danger underline">
            Reintentar
          </button>
        </div>
      ) : reglas.length === 0 ? (
        <EstadoVacio icono={Tag} titulo="Aún no tienes reglas creadas" texto="Una regla clasifica sola los movimientos que se repiten." className="mx-6 mt-6" />
      ) : (
        <div className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
          {reglas.map((r) => (
            <div key={r.id} className="flex items-center gap-3 px-4 py-3.5">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">"{r.patron}"</p>
                <p className="text-xs text-ink-soft">→ {r.categoria}{r.tipo ? ` · ${r.tipo}` : ''}</p>
              </div>
              <button onClick={() => eliminar(r.id)} className="w-11 h-11 -mr-1.5 flex items-center justify-center text-danger shrink-0" aria-label="Eliminar">
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      {mostrarForm && (
        <FormRegla
          onClose={() => setMostrarForm(false)}
          onGuardado={() => {
            setMostrarForm(false)
            cargar()
          }}
        />
      )}
    </div>
  )
}

function FormRegla({ onClose, onGuardado }) {
  const { nombres: categoriasSugeridas } = useCategorias()
  const [patron, setPatron] = useState('')
  const [categoria, setCategoria] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!patron.trim()) return setError('Escribe el texto a buscar')
    if (!categoria) return setError('Elige una categoría')

    setGuardando(true)
    try {
      await api.crearReglaCategoria({ patron: patron.trim(), categoria })
      onGuardado()
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Nueva regla</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      <input
        value={patron}
        onChange={(e) => setPatron(e.target.value)}
        placeholder="Texto a buscar (ej. Netflix, Uber)"
        className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
      />

      <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Categoría</p>
      <div className="grid grid-cols-3 gap-2 mb-4">
        {categoriasSugeridas.map((c) => (
          <button
            key={c}
            onClick={() => setCategoria(c)}
            className={`rounded-2xl border py-3 text-sm font-medium ${
              categoria === c ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-danger mb-3">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
      >
        {guardando ? 'Guardando...' : 'Guardar regla'}
      </button>
    </Hoja>
  )
}
