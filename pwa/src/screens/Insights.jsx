import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { AlertTriangle, ArrowLeft, ChevronRight, Clock, PieChart, Send, Sparkles, TrendingUp, Zap } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP, formatVeces } from '../lib/format'
import { rangoPeriodo } from '../lib/informe'
import MapaActividad from '../components/MapaActividad'
import SelectorPeriodo from '../components/SelectorPeriodo'

const PERIODOS_RESUMEN = [
  { id: '7_dias', label: 'Semana' },
  { id: '30_dias', label: '30 días' },
  { id: 'este_mes', label: 'Este mes' },
  { id: 'mes_pasado', label: 'Mes pasado' },
  { id: 'rango', label: 'Personalizado' },
]

const PREGUNTAS_SUGERIDAS = [
  '¿En qué gasté más este mes?',
  '¿Cuánto gasté en comida el mes pasado?',
  '¿Gasté más o menos que el mes pasado?',
  '¿Voy bien con mi presupuesto?',
]

export default function Insights() {
  const volver = useVolver('/')
  const [resumen, setResumen] = useState(null)
  const [edadDinero, setEdadDinero] = useState(null)
  const [alertas, setAlertas] = useState(null)
  const [periodoResumen, setPeriodoResumen] = useState({ periodo: '7_dias', ...rangoPeriodo('7_dias') })
  const [cargando, setCargando] = useState(true)
  const [mensajes, setMensajes] = useState([])
  const [pregunta, setPregunta] = useState('')
  const [enviando, setEnviando] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    api.edadDelDinero().then(setEdadDinero).catch(() => {})
    api.alertasProactivas().then(setAlertas).catch(() => {})
  }, [])

  useEffect(() => {
    let activo = true
    api.resumenSemanal(periodoResumen.desde, periodoResumen.hasta)
      .then((r) => activo && setResumen(r))
      .catch(() => {})
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [periodoResumen.desde, periodoResumen.hasta])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes])

  async function enviarPregunta(e, forzada) {
    e?.preventDefault()
    const texto = (forzada ?? pregunta).trim()
    if (!texto || enviando) return
    setPregunta('')
    setMensajes((prev) => [...prev, { rol: 'usuario', texto }])
    setEnviando(true)
    try {
      const { respuesta, sugerencias } = await api.preguntar(texto)
      setMensajes((prev) => [...prev, { rol: 'asistente', texto: respuesta, sugerencias }])
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
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Insights</h1>
      </header>

      <Link
        to="/informe"
        className="mx-6 mt-4 card-marca bg-accent-soft border border-accent/20 p-3.5 flex items-center gap-3"
      >
        <span className="w-10 h-10 rounded-xl bg-paper-raised flex items-center justify-center shrink-0">
          <PieChart size={18} className="text-accent" />
        </span>
        <div className="flex-1">
          <p className="text-sm font-semibold">En qué gasto mi plata</p>
          <p className="text-xs text-ink-soft mt-0.5">Informe por categoría y comercio, con el periodo que elijas</p>
        </div>
        <ChevronRight size={16} className="text-ink-soft shrink-0" />
      </Link>

      <MapaActividad />

      <section className="mx-6 mt-5">
        <SelectorPeriodo
          opciones={PERIODOS_RESUMEN}
          valor={periodoResumen}
          onChange={setPeriodoResumen}
          etiqueta="Periodo del resumen"
        />
      </section>

      {!cargando && resumen && (
        <>
          <section className="mx-6 mt-4 rounded-2xl bg-accent-soft p-4">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles size={16} className="text-accent" />
              <p className="text-xs font-semibold text-accent">{`Resumen ${(resumen.etiqueta || "de la semana").startsWith("del ") ? "" : "de "}${resumen.etiqueta || "la semana"}`}</p>
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
                      {formatCOP(c.total_mes)} en comisiones este mes ({formatVeces(c.veces)}) — vale la pena revisar si se puede evitar
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
            <div>
              <p className="text-xs text-ink-soft mb-2">Respondo con tus cifras reales y te digo el periodo. Prueba:</p>
              <div className="flex flex-wrap gap-1.5">
                {PREGUNTAS_SUGERIDAS.map((q) => (
                  <button key={q} type="button" onClick={() => enviarPregunta(null, q)} className="text-xs rounded-full border border-line bg-paper px-3 py-1.5 min-h-[34px]">
                    {q}
                  </button>
                ))}
              </div>
            </div>
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
              {m.sugerencias?.length > 0 && (
                <span className="flex flex-wrap gap-1.5 mt-2">
                  {m.sugerencias.map((q) => (
                    <button key={q} type="button" onClick={() => enviarPregunta(null, q)} className="text-xs rounded-full border border-line bg-paper-raised px-3 py-1.5 min-h-[32px]">
                      {q}
                    </button>
                  ))}
                </span>
              )}
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
