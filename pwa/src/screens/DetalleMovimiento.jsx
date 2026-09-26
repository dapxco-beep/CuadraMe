import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Trash2 } from 'lucide-react'
import { formatCOP } from '../lib/format'
import { api } from '../lib/api'

export default function DetalleMovimiento() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [movimiento, setMovimiento] = useState(null)
  const [eliminando, setEliminando] = useState(false)

  useEffect(() => {
    api
      .movimientos(500)
      .then((movs) => setMovimiento(movs.find((m) => m.id === id) || null))
      .catch(() => {})
  }, [id])

  async function eliminar() {
    setEliminando(true)
    try {
      await api.eliminarMovimiento(id)
      navigate('/movimientos')
    } catch {
      setEliminando(false)
    }
  }

  if (!movimiento) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-ink-soft">Cargando...</p>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col pb-6">
      <header className="px-5 pt-14 pb-2 flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="w-9 h-9 rounded-full bg-paper-raised border border-line flex items-center justify-center"
        >
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-semibold">Detalle del movimiento</h1>
      </header>

      <div className="flex flex-col items-center justify-center py-10">
        <span className="w-16 h-16 rounded-full bg-accent-soft flex items-center justify-center text-2xl mb-4">
          💳
        </span>
        <p
          className={`text-4xl font-bold ${movimiento.tipo === 'income' ? 'text-accent' : 'text-ink'}`}
        >
          {movimiento.tipo === 'income' ? '+' : '-'}
          {formatCOP(movimiento.monto)}
        </p>
        <p className="text-sm text-ink-soft mt-2">{movimiento.descripcion}</p>
      </div>

      <div className="mx-5 rounded-2xl bg-paper-raised border border-line divide-y divide-line">
        <Fila label="Categoría" valor={movimiento.categoria} />
        <Fila label="Fecha" valor={new Date(movimiento.fecha).toLocaleString('es-CO')} />
        <Fila label="Tipo" valor={movimiento.tipo === 'income' ? 'Ingreso' : 'Gasto'} />
        <Fila label="Origen" valor={movimiento.fuente} />
        {movimiento.notas && <Fila label="Notas" valor={movimiento.notas} />}
      </div>

      <div className="px-5 mt-6">
        <button
          onClick={eliminar}
          disabled={eliminando}
          className="w-full flex items-center justify-center gap-2 rounded-2xl border border-danger/30 bg-danger-soft text-danger font-semibold py-4 text-[15px] disabled:opacity-60"
        >
          <Trash2 size={16} /> {eliminando ? 'Eliminando...' : 'Eliminar movimiento'}
        </button>
      </div>
    </div>
  )
}

function Fila({ label, valor }) {
  return (
    <div className="flex items-center justify-between px-4 py-3.5">
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="text-sm font-medium">{valor}</p>
    </div>
  )
}
