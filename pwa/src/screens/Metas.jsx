import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'

export default function Metas() {
  const navigate = useNavigate()
  const [metas, setMetas] = useState([])
  const [cargando, setCargando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [aportando, setAportando] = useState(null)

  async function cargar() {
    setCargando(true)
    try {
      setMetas(await api.metas())
    } catch {}
    setCargando(false)
  }

  useEffect(() => {
    cargar()
  }, [])

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
          <h1 className="text-xl font-semibold">Metas de ahorro</h1>
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
      ) : metas.length === 0 ? (
        <div className="mx-5 mt-6 rounded-2xl bg-paper-raised border border-line p-8 text-center">
          <p className="text-sm text-ink-soft">Aún no tienes metas de ahorro</p>
        </div>
      ) : (
        <div className="mx-5 mt-4 space-y-3">
          {metas.map((m) => (
            <div key={m.id} className="rounded-2xl bg-paper-raised border border-line p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-semibold">{m.nombre}</p>
                <p className="text-xs text-ink-soft">{m.progreso_pct}%</p>
              </div>
              <div className="h-2 rounded-full bg-line overflow-hidden mb-2">
                <div
                  className="h-full bg-accent rounded-full"
                  style={{ width: `${Math.min(100, m.progreso_pct)}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-xs text-ink-soft mb-3">
                <span>{formatCOP(m.monto_actual)}</span>
                <span>{formatCOP(m.monto_objetivo)}</span>
              </div>
              {m.eta_meses && !m.completada && (
                <p className="text-xs text-ink-soft mb-3">
                  A tu ritmo actual, la alcanzas en ~{m.eta_meses} {m.eta_meses === 1 ? 'mes' : 'meses'}
                </p>
              )}
              {m.completada ? (
                <p className="text-sm font-semibold text-accent">¡Meta completada! 🎉</p>
              ) : (
                <button
                  onClick={() => setAportando(m)}
                  className="w-full bg-ink text-paper font-semibold rounded-xl py-2.5 text-sm"
                >
                  Aportar
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {mostrarForm && (
        <FormMeta
          onClose={() => setMostrarForm(false)}
          onGuardada={() => {
            setMostrarForm(false)
            cargar()
          }}
        />
      )}

      {aportando && (
        <FormAporte
          meta={aportando}
          onClose={() => setAportando(null)}
          onAportado={() => {
            setAportando(null)
            cargar()
          }}
        />
      )}
    </div>
  )
}

function FormMeta({ onClose, onGuardada }) {
  const [nombre, setNombre] = useState('')
  const [montoObjetivo, setMontoObjetivo] = useState('')
  const [montoActual, setMontoActual] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a tu meta')
    if (!montoObjetivo || Number(montoObjetivo) <= 0) return setError('Ingresa un monto objetivo válido')

    setGuardando(true)
    try {
      await api.crearMeta({
        nombre: nombre.trim(),
        monto_objetivo: Number(montoObjetivo),
        monto_actual: Number(montoActual) || 0,
      })
      onGuardada()
    } catch (err) {
      setError(err.message || 'No se pudo crear la meta')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Nueva meta</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-paper-raised border border-line flex items-center justify-center">
            <X size={16} />
          </button>
        </div>

        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Nombre (ej. Viaje a Cartagena)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
        />
        <input
          value={montoObjetivo}
          onChange={(e) => setMontoObjetivo(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder="Monto objetivo (ej. 5000000)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
        />
        <input
          value={montoActual}
          onChange={(e) => setMontoActual(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder="Ya tienes ahorrado (opcional)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
        />

        {error && <p className="text-sm text-danger mb-3">{error}</p>}

        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : 'Crear meta'}
        </button>
      </div>
    </div>
  )
}

function FormAporte({ meta, onClose, onAportado }) {
  const [monto, setMonto] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!monto || Number(monto) <= 0) return setError('Ingresa un monto válido')

    setGuardando(true)
    try {
      await api.aportarMeta(meta.id, Number(monto))
      onAportado()
    } catch (err) {
      setError(err.message || 'No se pudo registrar el aporte')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Aportar a "{meta.nombre}"</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-paper-raised border border-line flex items-center justify-center">
            <X size={16} />
          </button>
        </div>

        <input
          value={monto}
          onChange={(e) => setMonto(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder="Monto a aportar"
          autoFocus
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
        />

        {error && <p className="text-sm text-danger mb-3">{error}</p>}

        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : 'Aportar'}
        </button>
      </div>
    </div>
  )
}
