import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Check, Plus, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'

const estadoColor = {
  pagado: 'text-accent',
  proximo: 'text-accent-2',
  vencido: 'text-danger',
  pendiente: 'text-ink-soft',
}

const estadoLabel = {
  pagado: 'Pagado este mes',
  proximo: 'Próximo a vencer',
  vencido: 'Vencido',
  pendiente: 'Pendiente',
}

export default function Recurrentes() {
  const navigate = useNavigate()
  const { recargar: recargarCuentas } = useCuentas()
  const [recs, setRecs] = useState([])
  const [cargando, setCargando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)

  async function cargar() {
    setCargando(true)
    try {
      setRecs(await api.recurrentes())
    } catch {}
    setCargando(false)
  }

  useEffect(() => {
    cargar()
  }, [])

  async function marcarPagado(id) {
    await api.marcarRecurrentePagado(id)
    await recargarCuentas()
    cargar()
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6">
      <header className="px-5 pt-14 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/perfil')}
            className="w-9 h-9 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          >
            <ArrowLeft size={18} />
          </button>
          <h1 className="text-xl font-semibold">Recurrentes</h1>
        </div>
        <button
          onClick={() => setMostrarForm(true)}
          className="w-10 h-10 rounded-full bg-accent text-white flex items-center justify-center"
        >
          <Plus size={20} />
        </button>
      </header>

      {cargando ? (
        <p className="text-sm text-ink-soft text-center mt-8">Cargando...</p>
      ) : recs.length === 0 ? (
        <div className="mx-5 mt-6 rounded-2xl bg-paper-raised border border-line p-8 text-center">
          <p className="text-sm text-ink-soft">Aún no tienes gastos o ingresos recurrentes</p>
        </div>
      ) : (
        <div className="mx-5 mt-4 rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
          {recs.map((r) => (
            <div key={r.id} className="flex items-center gap-3 px-4 py-3.5">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{r.nombre}</p>
                <p className={`text-xs ${estadoColor[r.estado]}`}>
                  {estadoLabel[r.estado]} · día {r.dia_del_mes}
                </p>
              </div>
              <p className={`text-sm font-semibold shrink-0 ${r.tipo === 'income' ? 'text-accent' : 'text-ink'}`}>
                {r.tipo === 'income' ? '+' : '-'}
                {formatCOP(r.monto)}
              </p>
              {r.estado !== 'pagado' && (
                <button
                  onClick={() => marcarPagado(r.id)}
                  className="w-8 h-8 rounded-full bg-accent-soft text-accent flex items-center justify-center shrink-0"
                >
                  <Check size={16} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {mostrarForm && (
        <FormRecurrente
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

function FormRecurrente({ onClose, onGuardado }) {
  const { cuentas } = useCuentas()
  const [nombre, setNombre] = useState('')
  const [monto, setMonto] = useState('')
  const [tipo, setTipo] = useState('expense')
  const [diaMes, setDiaMes] = useState('1')
  const [cuentaId, setCuentaId] = useState(cuentas[0]?.id || '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre')
    if (!monto || Number(monto) <= 0) return setError('Ingresa un monto válido')

    setGuardando(true)
    try {
      await api.crearRecurrente({
        nombre: nombre.trim(),
        monto: Number(monto),
        tipo,
        dia_del_mes: Number(diaMes) || 1,
        cuenta_id: cuentaId || null,
      })
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
          <h2 className="text-lg font-semibold">Nuevo recurrente</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-paper-raised border border-line flex items-center justify-center">
            <X size={16} />
          </button>
        </div>

        <div className="flex gap-2 mb-3">
          {[
            { id: 'expense', label: 'Gasto' },
            { id: 'income', label: 'Ingreso' },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTipo(t.id)}
              className={`flex-1 rounded-2xl py-2.5 text-sm font-semibold border ${
                tipo === t.id ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Nombre (ej. Netflix, Arriendo)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
        />
        <input
          value={monto}
          onChange={(e) => setMonto(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder="Monto"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
        />
        <input
          value={diaMes}
          onChange={(e) => setDiaMes(e.target.value.replace(/\D/g, '').slice(0, 2))}
          inputMode="numeric"
          placeholder="Día del mes (1-31)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
        />

        {error && <p className="text-sm text-danger mb-3">{error}</p>}

        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : 'Crear recurrente'}
        </button>
      </div>
    </div>
  )
}
