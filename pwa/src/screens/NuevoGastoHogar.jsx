import { textoError } from '../lib/textoError'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useDialogos } from '../lib/DialogosContext'
import InputMonto from '../components/InputMonto'

const MODOS = [
  { id: 'iguales', label: 'Iguales' },
  { id: 'montos', label: 'Montos' },
  { id: 'porcentajes', label: '%' },
]
const AYUDA = {
  iguales: 'Todos los elegidos pagan lo mismo.',
  montos: 'Escribe cuánto le toca a cada uno; debe sumar el total.',
  porcentajes: 'Escribe el porcentaje de cada uno; debe sumar 100.',
}

// Nuevo gasto del parche: qué, cuánto, quién pagó y cómo se reparte. Opcional: copiar MI parte a una cuenta mía.
export default function NuevoGastoHogar() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { avisar } = useDialogos()
  const { cuentas, recargar } = useCuentas()
  const { nombres: categorias } = useCategorias()
  const [h, setH] = useState(null)
  const [descripcion, setDescripcion] = useState('')
  const [total, setTotal] = useState('')
  const [modo, setModo] = useState('iguales')
  const [elegidos, setElegidos] = useState([])
  const [valores, setValores] = useState({})
  const [pagador, setPagador] = useState('')
  const [categoria, setCategoria] = useState('')
  const [copiar, setCopiar] = useState(false)
  const [cuentaId, setCuentaId] = useState('')
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    api.hogar(id).then((d) => {
      setH(d)
      const activos = d.miembros.filter((m) => m.activo)
      setElegidos(activos.map((m) => m.id))
      setPagador(d.mi_miembro_id)
    }).catch(() => navigate('/hogares', { replace: true }))
  }, [id, navigate])

  if (!h) return <div className="flex-1" />
  const activos = h.miembros.filter((m) => m.activo)
  const cuentasOk = cuentas.filter((c) => (c.moneda || 'COP') === h.moneda)
  const alternar = (mid) => setElegidos((e) => (e.includes(mid) ? e.filter((x) => x !== mid) : [...e, mid]))

  const puede = descripcion.trim() && Number(total) > 0 && elegidos.length > 0 && pagador && !guardando && (!copiar || cuentaId)

  async function guardar() {
    setGuardando(true)
    try {
      await api.crearGastoHogar(id, {
        descripcion: descripcion.trim(),
        total: Number(total),
        modo,
        participantes: elegidos.map((mid) => ({ id: mid, valor: modo === 'iguales' ? 1 : Number(valores[mid]) || 0 })),
        pagador_id: pagador,
        categoria: categoria || undefined,
        registrar_en_mi_cuenta: copiar,
        cuenta_id: copiar ? cuentaId : undefined,
      })
      if (copiar) recargar?.()
      navigate(`/hogares/${id}`, { replace: true })
    } catch (e) {
      avisar(textoError(e, 'guardar el gasto'))
      setGuardando(false)
    }
  }

  const campo = 'w-full rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm outline-none focus:border-accent'
  const chip = (a) => `rounded-2xl border px-3.5 py-2 text-sm font-medium ${a ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'}`
  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={() => navigate(`/hogares/${id}`)} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-2xl font-semibold truncate">Nuevo gasto</h1>
      </header>

      <div className="px-5 mt-3 flex flex-col gap-3">
        <input aria-label="Descripción" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="¿Qué se pagó? (ej. Mercado, Arriendo)" maxLength={120} className={campo} />
        <InputMonto entero aria-label="Total" value={total} onValor={setTotal} placeholder="Total" className={`${campo} text-right tabular-nums`} />
        {categorias?.length > 0 && (
          <select aria-label="Categoría" value={categoria} onChange={(e) => setCategoria(e.target.value)} className={campo}>
            <option value="">Sin categoría</option>
            {categorias.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
        <label className="text-xs text-ink-soft font-medium uppercase tracking-wide">
          ¿Quién pagó?
          <select value={pagador} onChange={(e) => setPagador(e.target.value)} className={`${campo} mt-1 normal-case tracking-normal text-ink`}>
            {activos.map((m) => <option key={m.id} value={m.id}>{m.soy_yo ? 'Yo' : m.apodo}</option>)}
          </select>
        </label>
      </div>

      <section className="px-5 mt-5">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">¿Entre quiénes se reparte?</p>
        <div className="flex flex-wrap gap-2">
          {activos.map((m) => (
            <button key={m.id} onClick={() => alternar(m.id)} aria-pressed={elegidos.includes(m.id)} className={chip(elegidos.includes(m.id))}>
              {m.soy_yo ? 'Yo' : m.apodo}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2 mt-3" role="radiogroup" aria-label="Cómo se reparte">
          {MODOS.map((m) => (
            <button key={m.id} role="radio" aria-checked={modo === m.id} onClick={() => setModo(m.id)} className={`rounded-2xl border py-2.5 text-sm font-semibold ${modo === m.id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'}`}>
              {m.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-ink-soft mt-2">{AYUDA[modo]}</p>
        {modo !== 'iguales' && (
          <ul className="mt-2 flex flex-col gap-2">
            {activos.filter((m) => elegidos.includes(m.id)).map((m) => (
              <li key={m.id} className="flex items-center gap-3">
                <span className="flex-1 min-w-0 truncate text-sm">{m.soy_yo ? 'Yo' : m.apodo}</span>
                <InputMonto entero={modo === 'montos'} aria-label={`${modo === 'montos' ? 'Monto' : 'Porcentaje'} de ${m.apodo}`} value={valores[m.id] || ''} onValor={(v) => setValores({ ...valores, [m.id]: v })} placeholder={modo === 'montos' ? 'Monto' : '%'} className="w-32 rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm text-right tabular-nums outline-none focus:border-accent" />
              </li>
            ))}
          </ul>
        )}
      </section>

      {cuentasOk.length > 0 && (
        <section className="px-5 mt-5">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={copiar} onChange={(e) => { setCopiar(e.target.checked); if (e.target.checked && !cuentaId) setCuentaId(cuentasOk[0].id) }} className="w-5 h-5" />
            Registrar también mi parte en una de mis cuentas
          </label>
          {copiar && (
            <select aria-label="Cuenta" value={cuentaId} onChange={(e) => setCuentaId(e.target.value)} className={`${campo} mt-2`}>
              {cuentasOk.map((c) => <option key={c.id} value={c.id}>{c.nombre} ({c.moneda})</option>)}
            </select>
          )}
          <p className="text-[11px] text-ink-soft mt-1">Solo se copia lo que te toca a ti, en tu cuenta. Los demás no ven tus cuentas.</p>
        </section>
      )}

      <div className="px-5 mt-6">
        <button onClick={guardar} disabled={!puede} className="w-full bg-ink text-paper rounded-2xl py-3.5 text-sm font-semibold disabled:opacity-40">
          {guardando ? 'Guardando…' : 'Guardar gasto'}
        </button>
      </div>
    </div>
  )
}
