import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import { api } from '../lib/api'

const categoriasRapidas = ['Comida', 'Transporte', 'Ocio', 'Hogar', 'Salud', 'Otros']

export default function Agregar() {
  const navigate = useNavigate()
  const [cuentas, setCuentas] = useState([])
  const [cuentaId, setCuentaId] = useState('')
  const [monto, setMonto] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [tipo, setTipo] = useState('expense')
  const [categoria, setCategoria] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .cuentas()
      .then((cs) => {
        setCuentas(cs)
        if (cs.length > 0) setCuentaId(cs[0].id)
      })
      .catch(() => {})
  }, [])

  async function onDescripcionBlur() {
    if (!descripcion.trim() || categoria) return
    try {
      const r = await api.clasificar({ descripcion })
      if (r.categoria !== 'Otros') setCategoria(r.categoria)
    } catch {}
  }

  async function guardar() {
    setError('')
    if (!cuentaId) return setError('Crea una cuenta primero')
    if (!monto || Number(monto) <= 0) return setError('Ingresa un monto válido')
    if (!descripcion.trim()) return setError('Ingresa una descripción')

    setGuardando(true)
    try {
      await api.crearMovimiento({
        cuenta_id: cuentaId,
        descripcion: descripcion.trim(),
        monto: Number(monto),
        tipo,
        categoria: categoria || undefined,
      })
      navigate('/')
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col pb-6">
      <header className="px-5 pt-14 pb-2 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Nuevo movimiento</h1>
        <button
          onClick={() => navigate('/')}
          className="w-9 h-9 rounded-full bg-paper-raised border border-line flex items-center justify-center"
        >
          <X size={18} />
        </button>
      </header>

      <div className="px-5 flex gap-2 mt-2">
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

      <div className="flex flex-col items-center justify-center px-8 py-8">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-semibold text-ink-soft">$</span>
          <input
            value={monto}
            onChange={(e) => setMonto(e.target.value.replace(/\D/g, ''))}
            placeholder="0"
            inputMode="numeric"
            className="bg-transparent outline-none text-6xl font-semibold text-center w-full tabular-nums placeholder:text-ink-soft/40"
          />
        </div>
        <p className="text-sm text-ink-soft mt-2">COP</p>
      </div>

      <div className="px-5 mb-4">
        <input
          value={descripcion}
          onChange={(e) => setDescripcion(e.target.value)}
          onBlur={onDescripcionBlur}
          placeholder="¿En qué fue? (ej. Éxito, Uber, Netflix)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
        />
      </div>

      {cuentas.length > 1 && (
        <div className="px-5 mb-4 flex gap-2 overflow-x-auto no-scrollbar">
          {cuentas.map((c) => (
            <button
              key={c.id}
              onClick={() => setCuentaId(c.id)}
              className={`shrink-0 text-sm px-4 py-1.5 rounded-full border ${
                cuentaId === c.id ? 'bg-accent text-white border-accent' : 'border-line text-ink-soft'
              }`}
            >
              {c.icono} {c.nombre}
            </button>
          ))}
        </div>
      )}

      <div className="px-5 mb-5">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Categoría</p>
        <div className="grid grid-cols-3 gap-2">
          {categoriasRapidas.map((c) => (
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
      </div>

      {error && <p className="px-5 text-sm text-danger mb-3">{error}</p>}

      <div className="px-5">
        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] active:scale-[0.98] transition-transform disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : 'Guardar movimiento'}
        </button>
      </div>
    </div>
  )
}
