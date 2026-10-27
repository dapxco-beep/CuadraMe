import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Copy } from 'lucide-react'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { ETIQUETA_ESTADO, porcentaje } from '../lib/colectas'

const COLOR_ESTADO = {
  pagado: 'bg-accent-soft text-accent',
  parcial: 'bg-paper text-ink border border-line',
  falta: 'bg-paper text-ink-soft border border-line',
}

// Vista de SOLO LECTURA que abre quien recibe el enlace (sin cuenta, sin iniciar sesión).
// Puede copiar cómo pagar y avisar «ya pagué» (el organizador lo confirma); no mueve plata ni cambia lo recogido.
export default function ColectaPublica() {
  const { token } = useParams()
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [enviando, setEnviando] = useState('')

  const cargar = () =>
    api
      .colectaPublica(token)
      .then(setD)
      .catch((e) => setError(e.status === 404 ? 'Esta vaca no existe o ya no se comparte.' : e.message || 'No se pudo cargar. Revisa tu conexión.'))
  useEffect(() => {
    cargar()
  }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  async function copiar() {
    try {
      await navigator.clipboard.writeText(d.datos_pago)
      setMensaje('Copiado')
    } catch {
      setMensaje('Mantén presionado el texto para copiarlo')
    }
  }

  async function yaPague(p) {
    setEnviando(p.id)
    try {
      await api.avisarPagoColecta(token, p.id)
      setMensaje(`Listo, ${p.nombre}: quien lleva la vaca lo confirmará`)
      await cargar()
    } catch (e) {
      setMensaje(e.message || 'No se pudo avisar. Intenta de nuevo.')
    }
    setEnviando('')
  }

  const pct = d ? porcentaje(d.recogido, d.meta) : 0
  return (
    <div className="flex-1 overflow-y-auto pb-10 screen-enter">
      <header className="px-5 pantalla-top pb-2">
        <p className="text-xs text-ink-soft font-semibold uppercase tracking-wide">CuadraMe · Vaca</p>
        <h1 className="text-2xl font-semibold mt-1 break-words">{d?.nombre || 'Vaca'}</h1>
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
              {d.estado === 'cerrada' && <p className="text-xs text-ink-soft mt-1">Esta vaca ya está cerrada.</p>}
            </div>
          </section>

          {d.datos_pago && d.estado !== 'cerrada' && (
            <section className="px-5 mt-3">
              <div className="rounded-2xl border border-accent bg-accent-soft p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-accent">Cómo pagar</p>
                <p className="text-sm mt-1 break-words select-all">{d.datos_pago}</p>
                <button onClick={copiar} className="mt-2 rounded-xl border border-line bg-paper-raised text-xs font-semibold px-3 py-2 flex items-center gap-1.5">
                  <Copy size={16} /> Copiar
                </button>
                <p className="text-[11px] text-ink-soft mt-2">Pagas desde tu banco o app, por fuera. Luego toca “Ya pagué” junto a tu nombre.</p>
              </div>
            </section>
          )}
          {mensaje && <p className="px-5 mt-2 text-xs text-ink-soft" role="status">{mensaje}</p>}

          <ul className="px-5 mt-4 flex flex-col gap-2">
            {d.participantes.map((p, i) => (
              <li key={p.id || `${p.nombre}-${i}`} className="rounded-2xl border border-line bg-paper-raised px-4 py-3 flex items-center justify-between gap-3">
                <span className="text-sm font-semibold truncate">{p.nombre}</span>
                <span className="shrink-0 flex items-center gap-2">
                  {p.estado !== 'pagado' && d.estado !== 'cerrada' && p.id && (
                    p.avisado ? (
                      <span className="text-xs text-ink-soft">Avisó</span>
                    ) : (
                      <button onClick={() => yaPague(p)} disabled={enviando === p.id} className="rounded-xl border border-line text-xs font-semibold px-3 py-1.5 disabled:opacity-40">
                        Ya pagué
                      </button>
                    )
                  )}
                  <span className={`text-xs font-semibold rounded-full px-2.5 py-1 ${COLOR_ESTADO[p.estado]}`}>{ETIQUETA_ESTADO[p.estado]}</span>
                </span>
              </li>
            ))}
          </ul>

          <section className="px-5 mt-8">
            <div className="rounded-2xl border border-line bg-paper-raised p-4 text-center">
              <p className="text-sm font-semibold">¿Armas vacas con tus amigos?</p>
              <p className="text-xs text-ink-soft mt-1">Crea la tuya gratis en CuadraMe: ves quién puso y quién falta.</p>
              <a href="/" className="mt-3 inline-block bg-ink text-paper rounded-2xl px-5 py-3 text-sm font-semibold">Crear mi vaca gratis</a>
            </div>
          </section>
        </>
      )}
      <p className="px-5 mt-6 text-[11px] text-ink-soft">Solo se muestra el avance. CuadraMe no mueve plata ni muestra cuentas ni movimientos de nadie.</p>
    </div>
  )
}
