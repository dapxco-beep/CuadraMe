import { textoError } from '../lib/textoError'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'

function mesActual() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}
function moverMes(mes, delta) {
  const [a, m] = mes.split('-').map(Number)
  const d = new Date(a, m - 1 + delta, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}
function etiquetaMes(mes) {
  const [a, m] = mes.split('-').map(Number)
  return new Date(a, m - 1, 1).toLocaleDateString('es-CO', { month: 'long', year: 'numeric' })
}

// Resumen del mes del parche: cuánto puso (pagó) y cuánto consumió (su parte) cada quien, y en qué se fue.
export default function ResumenHogar() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [mes, setMes] = useState(mesActual())
  const [r, setR] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setR(null)
    setError('')
    api.resumenHogar(id, mes).then(setR).catch((e) => setError(textoError(e, 'cargar el resumen')))
  }, [id, mes])

  const maxCat = r ? Math.max(...r.por_categoria.map((c) => c.monto), 1) : 1
  return (
    <div className="flex-1 overflow-y-auto pb-10 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={() => navigate(`/hogares/${id}`)} className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-2xl font-semibold truncate">Resumen del mes</h1>
      </header>

      <div className="px-5 mt-2 flex items-center justify-between">
        <button onClick={() => setMes(moverMes(mes, -1))} className="w-11 h-11 rounded-full border border-line flex items-center justify-center" aria-label="Mes anterior"><ChevronLeft size={20} /></button>
        <p className="text-sm font-semibold capitalize">{etiquetaMes(mes)}</p>
        <button onClick={() => setMes(moverMes(mes, 1))} disabled={mes >= mesActual()} className="w-11 h-11 rounded-full border border-line flex items-center justify-center disabled:opacity-30" aria-label="Mes siguiente"><ChevronRight size={20} /></button>
      </div>

      {error && <p className="px-5 mt-6 text-sm text-danger" role="alert">{error}</p>}
      {!r && !error && <p className="px-5 mt-6 text-sm text-ink-soft">Cargando…</p>}
      {r && (
        <>
          <section className="px-5 mt-4">
            <div className="rounded-2xl border border-line bg-paper-raised p-4">
              <p className="text-xs text-ink-soft uppercase tracking-wide font-medium">Gasto del parche</p>
              <p className="text-2xl font-semibold tabular-nums">{formatMoneda(r.total, r.moneda)}</p>
            </div>
          </section>

          {r.por_miembro.length === 0 ? (
            <p className="px-5 mt-6 text-sm text-ink-soft">No hay gastos en este mes.</p>
          ) : (
            <>
              <section className="px-5 mt-5">
                <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Por persona</p>
                <ul className="flex flex-col gap-2">
                  {r.por_miembro.map((p) => (
                    <li key={p.miembro_id} className="rounded-2xl border border-line bg-paper-raised px-4 py-3">
                      <p className="text-sm font-semibold truncate">{p.nombre}</p>
                      <p className="text-xs text-ink-soft tabular-nums mt-0.5">Puso {formatMoneda(p.puso, r.moneda)} · Le tocó {formatMoneda(p.consumio, r.moneda)}</p>
                    </li>
                  ))}
                </ul>
              </section>
              <section className="px-5 mt-5">
                <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">En qué se fue</p>
                <ul className="flex flex-col gap-3">
                  {r.por_categoria.map((c) => (
                    <li key={c.categoria}>
                      <div className="flex justify-between text-sm"><span className="truncate pr-2">{c.categoria}</span><span className="tabular-nums shrink-0">{formatMoneda(c.monto, r.moneda)}</span></div>
                      <div className="mt-1 h-2 rounded-full bg-line overflow-hidden"><div className="h-full bg-accent" style={{ width: `${Math.round((c.monto / maxCat) * 100)}%` }} /></div>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}
        </>
      )}
    </div>
  )
}
