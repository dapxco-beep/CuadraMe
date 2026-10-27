import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, PiggyBank, Plus } from 'lucide-react'
import { EsqueletoLista } from '../components/Esqueletos'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { porcentaje } from '../lib/colectas'

// Lista de colectas (vacas): inscripción del equipo, paseo, regalo. Cada tarjeta muestra el avance.
export default function Colectas() {
  const navigate = useNavigate()
  const [lista, setLista] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  const cargar = useCallback(async () => {
    setError('')
    try {
      setLista(await api.colectas())
    } catch (e) {
      setError(e.message || 'No se pudieron cargar las colectas. Revisa tu conexión e intenta de nuevo.')
    }
    setCargando(false)
  }, [])
  useEffect(() => {
    cargar()
  }, [cargar])

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => navigate('/agregar')}
            className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center"
            aria-label="Volver"
          >
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-2xl font-semibold truncate">Colectas</h1>
        </div>
        <button
          onClick={() => navigate('/colectas/nueva')}
          className="w-11 h-11 shrink-0 rounded-full bg-ink text-paper flex items-center justify-center"
          aria-label="Nueva colecta"
        >
          <Plus size={20} />
        </button>
      </header>

      {cargando && <EsqueletoLista filas={3} className="mx-5 mt-6" etiqueta="Cargando colectas" />}
      {error && (
        <div className="px-5 mt-6" role="alert">
          <p className="text-sm text-danger">{error}</p>
          <button onClick={cargar} className="text-sm text-accent font-medium mt-1">
            Reintentar
          </button>
        </div>
      )}

      {!cargando && !error && lista.length === 0 && (
        <div className="px-8 mt-16 text-center">
          <PiggyBank size={24} className="mx-auto text-ink-soft" aria-hidden="true" />
          <p className="font-semibold mt-2">Aún no tienes colectas</p>
          <p className="text-sm text-ink-soft mt-1">
            Para la inscripción del equipo, un paseo o un regalo: ves quién ya puso, quién falta, y se lo recuerdas por WhatsApp.
          </p>
          <button onClick={() => navigate('/colectas/nueva')} className="mt-4 bg-ink text-paper rounded-2xl px-5 py-3 text-sm font-semibold">
            Crear mi primera colecta
          </button>
        </div>
      )}

      <ul className="px-5 mt-3 flex flex-col gap-3">
        {lista.map((c) => {
          const pct = porcentaje(c.recogido, c.meta)
          return (
            <li key={c.id}>
              <button
                onClick={() => navigate(`/colectas/${c.id}`)}
                className="w-full text-left rounded-2xl border border-line bg-paper-raised p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold min-w-0 break-words">{c.nombre}</p>
                  {c.estado === 'cerrada' && (
                    <span className="shrink-0 text-[11px] text-ink-soft border border-line rounded-full px-2 py-0.5">Cerrada</span>
                  )}
                </div>
                <div
                  className="mt-2 h-2 rounded-full bg-line overflow-hidden"
                  role="progressbar"
                  aria-valuenow={pct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`Avance de ${c.nombre}`}
                >
                  <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
                </div>
                <p className="text-xs text-ink-soft mt-2 tabular-nums">
                  {formatMoneda(c.recogido, c.moneda)} de {formatMoneda(c.meta, c.moneda)} · {c.pagaron} de {c.personas} pagaron
                </p>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
