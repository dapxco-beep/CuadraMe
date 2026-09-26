import { useEffect, useState } from 'react'
import { Plus, X } from 'lucide-react'
import { formatCOP } from '../lib/format'
import { api } from '../lib/api'

const categoriasSugeridas = ['Comida', 'Transporte', 'Ocio', 'Hogar', 'Salud', 'Otros']

export default function Presupuesto() {
  const [presupuestos, setPresupuestos] = useState([])
  const [gastosPorCategoria, setGastosPorCategoria] = useState({})
  const [cargando, setCargando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)

  useEffect(() => {
    cargar()
  }, [])

  async function cargar() {
    setCargando(true)
    try {
      const [ps, reporte] = await Promise.all([api.presupuestos(), api.reporteMensual()])
      setPresupuestos(ps)
      const gastos = {}
      reporte.top_categorias.forEach((c) => {
        gastos[c.categoria] = c.monto
      })
      setGastosPorCategoria(gastos)
    } catch {}
    setCargando(false)
  }

  async function eliminar(id) {
    await api.eliminarPresupuesto(id)
    cargar()
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6">
      <header className="px-6 pt-14 pb-2 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Presupuesto</h1>
        <button
          onClick={() => setMostrarForm(true)}
          className="w-10 h-10 rounded-full bg-accent text-white flex items-center justify-center"
        >
          <Plus size={20} />
        </button>
      </header>

      {cargando ? (
        <p className="text-sm text-ink-soft text-center mt-8">Cargando...</p>
      ) : presupuestos.length === 0 ? (
        <div className="mx-6 mt-6 rounded-2xl bg-paper-raised border border-line p-8 text-center">
          <p className="text-sm text-ink-soft">Aún no tienes presupuestos definidos</p>
          <button
            onClick={() => setMostrarForm(true)}
            className="mt-4 text-sm text-accent font-medium"
          >
            Crear el primero
          </button>
        </div>
      ) : (
        <div className="mx-6 mt-4 space-y-3">
          {presupuestos.map((p) => {
            const gastado = gastosPorCategoria[p.categoria] || 0
            const pct = Math.min(100, Math.round((gastado / p.limite) * 100))
            const alerta = pct >= p.alerta_pct
            return (
              <div key={p.id} className="rounded-2xl bg-paper-raised border border-line p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-semibold">{p.categoria}</p>
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-ink-soft">
                      {formatCOP(gastado)} / {formatCOP(p.limite)}
                    </p>
                    <button onClick={() => eliminar(p.id)} className="text-ink-soft">
                      <X size={14} />
                    </button>
                  </div>
                </div>
                <div className="h-2 rounded-full bg-line overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${pct}%`,
                      background: alerta ? 'var(--color-danger)' : 'var(--color-accent)',
                    }}
                  />
                </div>
                {alerta && (
                  <p className="text-xs text-danger mt-1.5">Te acercas al límite de este mes</p>
                )}
              </div>
            )
          })}
        </div>
      )}

      {mostrarForm && (
        <FormPresupuesto
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

function FormPresupuesto({ onClose, onGuardado }) {
  const [categoria, setCategoria] = useState('')
  const [limite, setLimite] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!categoria) return setError('Elige una categoría')
    if (!limite || Number(limite) <= 0) return setError('Ingresa un límite válido')

    setGuardando(true)
    try {
      await api.crearPresupuesto({ categoria, limite: Number(limite) })
      onGuardado()
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Nuevo presupuesto</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-paper-raised border border-line flex items-center justify-center">
            <X size={16} />
          </button>
        </div>

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

        <input
          value={limite}
          onChange={(e) => setLimite(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder="Límite mensual (ej. 500000)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
        />

        {error && <p className="text-sm text-danger mb-3">{error}</p>}

        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : 'Guardar presupuesto'}
        </button>
      </div>
    </div>
  )
}
