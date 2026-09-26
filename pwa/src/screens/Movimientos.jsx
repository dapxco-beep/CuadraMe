import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { formatCOP } from '../lib/format'
import { api } from '../lib/api'

export default function Movimientos() {
  const [movimientos, setMovimientos] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [filtro, setFiltro] = useState('Todos')
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    api
      .movimientos(200)
      .then(setMovimientos)
      .catch(() => {})
      .finally(() => setCargando(false))
  }, [])

  const categorias = ['Todos', ...new Set(movimientos.map((m) => m.categoria))]

  const filtrados = movimientos.filter((m) => {
    const coincideBusqueda = m.descripcion.toLowerCase().includes(busqueda.toLowerCase())
    const coincideFiltro = filtro === 'Todos' || m.categoria === filtro
    return coincideBusqueda && coincideFiltro
  })

  return (
    <div className="flex-1 overflow-y-auto pb-6">
      <header className="px-5 pt-14 pb-4">
        <h1 className="text-2xl font-semibold">Movimientos</h1>
      </header>

      <div className="px-5 mb-4">
        <div className="flex items-center gap-2 bg-paper-raised border border-line rounded-2xl px-4 py-3">
          <Search size={18} className="text-ink-soft" />
          <input
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar movimiento"
            className="bg-transparent outline-none text-sm flex-1 placeholder:text-ink-soft"
          />
        </div>
      </div>

      {categorias.length > 1 && (
        <div className="px-5 flex gap-2 mb-4 overflow-x-auto no-scrollbar">
          {categorias.map((f) => (
            <button
              key={f}
              onClick={() => setFiltro(f)}
              className={`shrink-0 text-sm px-4 py-1.5 rounded-full border ${
                filtro === f ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      )}

      {cargando ? (
        <p className="text-sm text-ink-soft text-center mt-8">Cargando...</p>
      ) : filtrados.length === 0 ? (
        <div className="mx-5 rounded-3xl bg-paper-raised border border-line p-8 text-center">
          <p className="text-sm text-ink-soft">No hay movimientos que coincidan</p>
        </div>
      ) : (
        <section className="mx-5 rounded-3xl bg-paper-raised border border-line overflow-hidden">
          {filtrados.map((m, i) => (
            <Link
              key={m.id}
              to={`/movimientos/${m.id}`}
              className={`flex items-center gap-3 px-5 py-3.5 ${i !== 0 ? 'border-t border-line' : ''}`}
            >
              <span className="w-10 h-10 rounded-full bg-accent-soft flex items-center justify-center text-lg shrink-0">
                💳
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{m.descripcion}</p>
                <p className="text-xs text-ink-soft">
                  {m.categoria} · {new Date(m.fecha).toLocaleDateString('es-CO')}
                </p>
              </div>
              <span className={`text-sm font-semibold shrink-0 ${m.tipo === 'income' ? 'text-accent' : 'text-ink'}`}>
                {m.tipo === 'income' ? '+' : '-'}
                {formatCOP(m.monto)}
              </span>
            </Link>
          ))}
        </section>
      )}
    </div>
  )
}
