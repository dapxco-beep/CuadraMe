import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Home, Plus } from 'lucide-react'
import { EsqueletoLista } from '../components/Esqueletos'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { useDialogos } from '../lib/DialogosContext'

// Mis hogares (pareja, familia, compañeros de casa): libro común de gastos entre personas con cuenta.
export default function Hogares() {
  const navigate = useNavigate()
  const { avisar } = useDialogos()
  const [lista, setLista] = useState([])
  const [invitaciones, setInvitaciones] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [nuevo, setNuevo] = useState(null)

  const cargar = useCallback(async () => {
    setError('')
    try {
      const [hs, inv] = await Promise.all([api.hogares(), api.misInvitacionesHogar().catch(() => [])])
      setLista(hs)
      setInvitaciones(inv)
    } catch (e) {
      setError(e.message || 'No se pudieron cargar tus parches. Revisa tu conexión e intenta de nuevo.')
    }
    setCargando(false)
  }, [])
  useEffect(() => {
    cargar()
  }, [cargar])

  async function crear() {
    if (!nuevo?.nombre.trim()) return
    try {
      const r = await api.crearHogar({ nombre: nuevo.nombre.trim() })
      navigate(`/hogares/${r.id}`)
    } catch (e) {
      avisar(e.message || 'No se pudo crear el parche. Intenta de nuevo.')
    }
  }

  const campo = 'w-full rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm outline-none focus:border-accent'
  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <button onClick={() => navigate('/agregar')} className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Volver">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-2xl font-semibold truncate">Parche</h1>
        </div>
        <button onClick={() => setNuevo({ nombre: '' })} className="w-11 h-11 shrink-0 rounded-full bg-ink text-paper flex items-center justify-center" aria-label="Nuevo parche">
          <Plus size={20} />
        </button>
      </header>

      {invitaciones.length > 0 && (
        <section className="px-5 mt-2 flex flex-col gap-2" aria-label="Invitaciones">
          {invitaciones.map((i) => (
            <button key={i.token} onClick={() => navigate(`/unirse/${i.token}`)} className="w-full text-left rounded-2xl border border-accent bg-accent-soft p-4">
              <p className="text-sm font-semibold text-accent">Te invitaron a “{i.hogar}”</p>
              <p className="text-xs text-ink-soft mt-0.5">Toca para unirte</p>
            </button>
          ))}
        </section>
      )}

      {nuevo && (
        <div className="px-5 mt-3">
          <div className="rounded-2xl border border-line bg-paper-raised p-3 flex flex-col gap-2">
            <input aria-label="Nombre del parche" autoFocus value={nuevo.nombre} onChange={(e) => setNuevo({ nombre: e.target.value })} placeholder="Nombre (ej. Casa, Apartamento, Viaje)" maxLength={60} className={campo} />
            <div className="flex gap-2">
              <button onClick={crear} disabled={!nuevo.nombre.trim()} className="flex-1 bg-ink text-paper rounded-2xl py-2.5 text-sm font-semibold disabled:opacity-40">Crear parche</button>
              <button onClick={() => setNuevo(null)} className="px-4 text-sm text-ink-soft">Cancelar</button>
            </div>
          </div>
        </div>
      )}

      {cargando && <EsqueletoLista filas={2} className="mx-5 mt-6" etiqueta="Cargando parches" />}
      {error && (
        <div className="px-5 mt-6" role="alert">
          <p className="text-sm text-danger">{error}</p>
          <button onClick={cargar} className="text-sm text-accent font-medium mt-1">Reintentar</button>
        </div>
      )}

      {!cargando && !error && lista.length === 0 && !nuevo && (
        <div className="px-8 mt-16 text-center">
          <Home size={24} className="mx-auto text-ink-soft" aria-hidden="true" />
          <p className="font-semibold mt-2">Aún no tienes un parche</p>
          <p className="text-sm text-ink-soft mt-1">
            Para la pareja, la familia o los compañeros de casa: cada quien con su cuenta, un libro común, y saber quién le debe a quién.
          </p>
          <button onClick={() => setNuevo({ nombre: '' })} className="mt-4 bg-ink text-paper rounded-2xl px-5 py-3 text-sm font-semibold">
            Crear mi primer parche
          </button>
        </div>
      )}

      <ul className="px-5 mt-3 flex flex-col gap-3">
        {lista.map((h) => (
          <li key={h.id}>
            <button onClick={() => navigate(`/hogares/${h.id}`)} className="w-full text-left rounded-2xl border border-line bg-paper-raised p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold min-w-0 break-words">{h.nombre}</p>
                <span className="shrink-0 text-xs text-ink-soft">{h.miembros} {h.miembros === 1 ? 'persona' : 'personas'}</span>
              </div>
              <p className={`text-xs mt-2 tabular-nums ${h.mi_saldo > 0 ? 'text-accent' : h.mi_saldo < 0 ? 'text-danger' : 'text-ink-soft'}`}>
                {h.mi_saldo > 0 ? `Te deben ${formatMoneda(h.mi_saldo, h.moneda)}` : h.mi_saldo < 0 ? `Debes ${formatMoneda(-h.mi_saldo, h.moneda)}` : 'Estás a mano'}
              </p>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
