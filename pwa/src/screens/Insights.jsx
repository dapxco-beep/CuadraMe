import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, Clock, Send, Sparkles, TrendingUp, Zap } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { tipoEfectivo } from '../lib/contabilidad'

function construirMapaCalor(movimientos) {
  const gastoPorDia = {}
  for (const m of movimientos) {
    if (tipoEfectivo(m) !== 'expense') continue
    const dia = m.fecha.slice(0, 10)
    gastoPorDia[dia] = (gastoPorDia[dia] || 0) + m.monto
  }

  const hoy = new Date()
  const dias = []
  for (let i = 34; i >= 0; i--) {
    const fecha = new Date(hoy)
    fecha.setDate(hoy.getDate() - i)
    const key = fecha.toISOString().slice(0, 10)
    dias.push({ key, monto: gastoPorDia[key] || 0 })
  }

  const max = Math.max(1, ...dias.map((d) => d.monto))
  return dias.map((d) => ({ ...d, intensidad: d.monto / max }))
}

function colorIntensidad(intensidad) {
  if (intensidad === 0) return 'var(--color-line)'
  if (intensidad < 0.25) return 'color-mix(in srgb, var(--color-accent) 30%, var(--color-paper-raised))'
  if (intensidad < 0.55) return 'color-mix(in srgb, var(--color-accent) 60%, var(--color-paper-raised))'
  if (intensidad < 0.85) return 'var(--color-accent)'
  return 'var(--color-danger)'
}

export default function Insights() {
  const navigate = useNavigate()
  const [resumen, setResumen] = useState(null)
  const [edadDinero, setEdadDinero] = useState(null)
  const [alertas, setAlertas] = useState(null)
  const [mapaCalor, setMapaCalor] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [mensajes, setMensajes] = useState([])
  const [pregunta, setPregunta] = useState('')
  const [enviando, setEnviando] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    api.resumenSemanal().then(setResumen).catch(() => {}).finally(() => setCargando(false))
    api.edadDelDinero().then(setEdadDinero).catch(() => {})
    api.alertasProactivas().then(setAlertas).catch(() => {})
    api.movimientos(200).then((movs) => setMapaCalor(construirMapaCalor(movs))).catch(() => {})
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes])

  async function enviarPregunta(e) {
    e.preventDefault()
    const texto = pregunta.trim()
    if (!texto || enviando) return
    setPregunta('')
    setMensajes((prev) => [...prev, { rol: 'usuario', texto }])
    setEnviando(true)
    try {
      const { respuesta } = await api.preguntar(texto)
      setMensajes((prev) => [...prev, { rol: 'asistente', texto: respuesta }])
    } catch (err) {
      setMensajes((prev) => [
        ...prev,
        { rol: 'asistente', texto: err.message || 'No pude responder eso — intenta de nuevo en un momento' },
      ])
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 flex flex-col">
      <header className="px-6 pt-14 pb-2 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="w-9 h-9 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Insights</h1>
      </header>

      {mapaCalor && (
        <section className="mx-6 mt-4">
          <p className="text-[11px] font-bold text-ink-soft uppercase tracking-wide mb-2.5">
            Tu gasto día a día (últimas 5 semanas)
          </p>
          <div className="grid grid-cols-7 gap-1.5">
            {mapaCalor.map((d, i) => (
              <div
                key={d.key}
                className="aspect-square rounded-[6px] pop-in"
                style={{ background: colorIntensidad(d.intensidad), animationDelay: `${Math.min(i, 20) * 12}ms` }}
                title={`${d.key}: ${formatCOP(d.monto)}`}
              />
            ))}
          </div>
          <div className="flex items-center gap-1.5 mt-2.5 text-[10px] text-ink-soft">
            <span>Menos</span>
            <span className="w-2.5 h-2.5 rounded-[3px]" style={{ background: 'var(--color-line)' }} />
            <span className="w-2.5 h-2.5 rounded-[3px]" style={{ background: 'color-mix(in srgb, var(--color-accent) 30%, var(--color-paper-raised))' }} />
            <span className="w-2.5 h-2.5 rounded-[3px]" style={{ background: 'color-mix(in srgb, var(--color-accent) 60%, var(--color-paper-raised))' }} />
            <span className="w-2.5 h-2.5 rounded-[3px]" style={{ background: 'var(--color-accent)' }} />
            <span className="w-2.5 h-2.5 rounded-[3px]" style={{ background: 'var(--color-danger)' }} />
            <span>Más</span>
          </div>
        </section>
      )}

      {!cargando && resumen && (
        <>
          <section className="mx-6 mt-4 rounded-2xl bg-accent-soft p-4">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles size={16} className="text-accent" />
              <p className="text-xs font-semibold text-accent">Resumen de la semana</p>
            </div>
            <p className="text-sm text-ink leading-relaxed">{resumen.texto}</p>
            <div className="flex items-center gap-4 mt-3 text-xs text-ink-soft">
              <span>Ingresos {formatCOP(resumen.ingresos)}</span>
              <span>Gastos {formatCOP(resumen.gastos)}</span>
            </div>
          </section>

          {edadDinero && edadDinero.dias > 0 && (
            <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-4">
              <p className="text-xs text-ink-soft">Tu colchón te alcanza para</p>
              <div className="flex items-center gap-4 mt-1">
                <div className="w-14 h-14 rounded-full bg-accent-soft flex items-center justify-center shrink-0">
                  <Clock size={20} className="text-accent" />
                </div>
                <div className="flex-1">
                  <p className="text-2xl font-bold">{edadDinero.dias} días</p>
                  <p className="text-xs text-ink-soft mt-0.5">{edadDinero.mensaje}</p>
                </div>
              </div>
              <p className="text-[11px] text-ink-soft mt-3 pt-3 border-t border-line">
                Es lo que los expertos llaman <b>"edad del dinero"</b>: cuántos días podrías vivir con lo
                que tienes hoy si dejaras de recibir ingresos — entre más días, más colchón para un imprevisto.
              </p>
            </section>
          )}

          {alertas && (alertas.comisiones.length > 0 || alertas.cobros_duplicados.length > 0) && (
            <section className="mx-6 mt-4">
              <div className="flex items-center gap-2 mb-2">
                <Zap size={16} className="text-accent-2" />
                <h2 className="text-[15px] font-semibold">Cosas que detectamos por ti</h2>
              </div>
              <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
                {alertas.comisiones.map((c) => (
                  <div key={c.descripcion} className="px-4 py-3">
                    <p className="text-sm font-medium">{c.descripcion}</p>
                    <p className="text-xs text-ink-soft mt-0.5">
                      {formatCOP(c.total_mes)} en comisiones este mes ({c.veces} {c.veces === 1 ? 'vez' : 'veces'}) — vale la pena revisar si se puede evitar
                    </p>
                  </div>
                ))}
                {alertas.cobros_duplicados.map((d) => (
                  <div key={d.movimiento_id_1} className="px-4 py-3">
                    <p className="text-sm font-medium">Posible cobro duplicado: {d.descripcion}</p>
                    <p className="text-xs text-ink-soft mt-0.5">
                      {formatCOP(d.monto)} cobrado dos veces en menos de 48 horas — si fue un error, puedes reclamarlo
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {resumen.anomalias.length > 0 && (
            <section className="mx-6 mt-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={16} className="text-accent-2" />
                <h2 className="text-[15px] font-semibold">Fuera de lo normal</h2>
              </div>
              <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
                {resumen.anomalias.map((a) => (
                  <div key={a.categoria} className="px-4 py-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium">{a.categoria}</p>
                      <p className="text-sm font-bold text-accent-2">+{a.variacion_pct}%</p>
                    </div>
                    <p className="text-xs text-ink-soft mt-0.5">
                      {formatCOP(a.monto_actual)} este mes vs. {formatCOP(a.promedio_historico)} promedio
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <section className="mx-6 mt-6">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp size={16} className="text-ink-soft" />
          <h2 className="text-[15px] font-semibold">Pregúntale a tus finanzas</h2>
        </div>

        <div className="rounded-2xl bg-paper-raised border border-line p-4 min-h-[120px] flex flex-col gap-3">
          {mensajes.length === 0 && (
            <p className="text-xs text-ink-soft">
              Ej: "¿Cuánto gasté en comida este mes?" o "¿Voy bien con mi presupuesto?"
            </p>
          )}
          {mensajes.map((m, i) => (
            <div
              key={i}
              className={`text-sm rounded-2xl px-3.5 py-2.5 max-w-[85%] ${
                m.rol === 'usuario'
                  ? 'bg-ink text-paper self-end'
                  : 'bg-paper border border-line self-start'
              }`}
            >
              {m.texto}
            </div>
          ))}
          {enviando && <p className="text-xs text-ink-soft self-start">Pensando...</p>}
          <div ref={scrollRef} />
        </div>

        <form onSubmit={enviarPregunta} className="flex gap-2 mt-3">
          <input
            value={pregunta}
            onChange={(e) => setPregunta(e.target.value)}
            placeholder="Escribe tu pregunta..."
            className="flex-1 rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={enviando || !pregunta.trim()}
            className="w-12 h-12 shrink-0 rounded-2xl bg-ink text-paper flex items-center justify-center disabled:opacity-50"
          >
            <Send size={16} />
          </button>
        </form>
      </section>
    </div>
  )
}
