import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { ETIQUETA_ESTADO, porcentaje } from '../lib/colectas'

const COLOR_ESTADO = {
  pagado: 'bg-accent-soft text-accent',
  parcial: 'bg-paper text-ink border border-line',
  falta: 'bg-paper text-ink-soft border border-line',
}

// Vista de SOLO LECTURA que abre quien recibe el enlace (sin cuenta, sin iniciar sesión).
export default function ColectaPublica() {
  const { token } = useParams()
  const [d, setD] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .colectaPublica(token)
      .then(setD)
      .catch((e) => setError(e.status === 404 ? 'Esta colecta no existe o ya no se comparte.' : e.message || 'No se pudo cargar. Revisa tu conexión.'))
  }, [token])

  const pct = d ? porcentaje(d.recogido, d.meta) : 0
  return (
    <div className="flex-1 overflow-y-auto pb-10 screen-enter">
      <header className="px-5 pantalla-top pb-2">
        <p className="text-xs text-ink-soft font-semibold uppercase tracking-wide">CuadraMe · Colecta</p>
        <h1 className="text-2xl font-semibold mt-1 break-words">{d?.nombre || 'Colecta'}</h1>
        {d?.descripcion && <p className="text-sm text-ink-soft mt-1">{d.descripcion}</p>}
      </header>

      {error && (
        <p className="px-5 mt-6 text-sm text-ink-soft" role="alert">
          {error}
        </p>
      )}
      {!d && !error && <p className="px-5 mt-6 text-sm text-ink-soft">Cargando…</p>}

      {d && (
        <>
          <section className="px-5 mt-3">
            <div className="rounded-2xl border border-line bg-paper-raised p-4">
              <p className="text-2xl font-semibold tabular-nums">{formatMoneda(d.recogido, d.moneda)}</p>
              <p className="text-xs text-ink-soft tabular-nums">de {formatMoneda(d.meta, d.moneda)} · faltan {formatMoneda(d.falta, d.moneda)}</p>
              <div className="mt-3 h-2.5 rounded-full bg-line overflow-hidden" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Avance">
                <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
              </div>
              {d.fecha_limite && (
                <p className="text-xs text-ink-soft mt-2">
                  Fecha límite: {new Date(d.fecha_limite).toLocaleDateString('es-CO', { day: 'numeric', month: 'long' })}
                </p>
              )}
              {d.estado === 'cerrada' && <p className="text-xs text-ink-soft mt-1">Esta colecta ya está cerrada.</p>}
            </div>
          </section>
          <ul className="px-5 mt-4 flex flex-col gap-2">
            {d.participantes.map((p, i) => (
              <li key={`${p.nombre}-${i}`} className="rounded-2xl border border-line bg-paper-raised px-4 py-3 flex items-center justify-between gap-3">
                <span className="text-sm font-semibold truncate">{p.nombre}</span>
                <span className={`shrink-0 text-xs font-semibold rounded-full px-2.5 py-1 ${COLOR_ESTADO[p.estado]}`}>{ETIQUETA_ESTADO[p.estado]}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="px-5 mt-8 text-[11px] text-ink-soft">Solo se muestra el avance. No hay cuentas ni movimientos de nadie.</p>
    </div>
  )
}
