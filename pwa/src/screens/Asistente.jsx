import { useEffect, useRef, useState } from 'react'
import { useVolver } from '../lib/useVolver'
import { AlertTriangle, ArrowLeft, Check, Info, Send, Sparkles, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP, formatPorcentaje } from '../lib/format'
import { Isotipo } from '../brand/Marca'
import Cuadri from '../brand/Cuadri'
import { FRASES, useMostrarCuadri } from '../lib/cuadri'
import { EVENTO_RESUELTO } from '../components/ConsentimientoGlobal'
import AvisoSinTasa from '../components/AvisoSinTasa'

// CuadraMe AI. Principios de esta pantalla:
//  - El asistente PROPONE; solo se guarda algo cuando el usuario toca "Confirmar".
//  - Las cifras vienen del backend (cálculo determinista); aquí solo se muestran.
//  - Cada respuesta indica de dónde sale ("Basado en: ...").
//  - La conversación vive solo en memoria de esta pantalla: no se guarda en ningún lado.

const VEREDICTO = {
  si: { texto: 'Puedes comprarlo', clase: 'text-accent' },
  ajustado: { texto: 'Alcanza, pero justo', clase: 'text-ink' },
  no_aun: { texto: 'Todavía no te alcanza', clase: 'text-danger' },
}

function Fuentes({ fuentes }) {
  if (!fuentes?.length) return null
  return (
    <p className="mt-2 text-[11px] text-ink-soft flex gap-1.5 items-start">
      <Info size={16} className="shrink-0 mt-0.5" aria-hidden="true" />
      <span>Basado en: {fuentes.join(' · ')}</span>
    </p>
  )
}

function TarjetaSimulacion({ c }) {
  const v = VEREDICTO[c.veredicto] || VEREDICTO.no_aun
  return (
    <div className="mt-3 card-marca-sm bg-paper border border-line p-3 text-xs space-y-1.5" aria-label="Detalle del cálculo">
      <p className={`text-sm font-bold ${v.clase}`}>{v.texto}</p>
      <Fila k="Precio" v={formatCOP(c.precio)} />
      <Fila k="Dinero realmente disponible" v={formatCOP(c.disponible_real)} />
      <Fila k="Colchón sugerido" v={formatCOP(c.colchon_sugerido)} />
      <Fila k="Te quedaría" v={formatCOP(c.quedaria_disponible)} fuerte />
      <Fila k="Capacidad de ahorro al mes" v={formatCOP(c.capacidad_ahorro_mensual)} />
      {c.veredicto !== 'si' && c.meses_ahorrando > 0 && <Fila k="Ahorrando, lo logras en" v={`${c.meses_ahorrando} meses`} />}
      <p className="pt-1.5 text-[11px] font-bold uppercase tracking-wide text-ink-soft">En cuotas</p>
      {c.cuotas.map((q) => (
        <div key={q.plazo_meses} className="flex justify-between gap-2">
          <span className="text-ink-soft">{q.plazo_meses} meses</span>
          <span className={q.cabe_en_tu_capacidad ? 'font-medium' : 'font-medium text-ink-soft'}>
            {formatCOP(q.cuota_con_interes)}/mes
          </span>
        </div>
      ))}
      <p className="text-[11px] text-ink-soft">Cuotas con {formatPorcentaje(c.tasa_mensual_referencia_pct, { decimales: 2 })} mensual de referencia; tu tarjeta real puede variar.</p>
    </div>
  )
}

function Fila({ k, v, fuerte }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-ink-soft">{k}</span>
      <span className={fuerte ? 'font-bold' : 'font-medium'}>{v}</span>
    </div>
  )
}

// Tarjeta de confirmación de un movimiento propuesto. Editable: cuenta y categoría.
function TarjetaPropuesta({ msg, onResuelto }) {
  const p = msg.propuesta
  const [cuentaId, setCuentaId] = useState(p.cuenta_id || '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function confirmar() {
    if (!cuentaId) {
      setError('Elige la cuenta')
      return
    }
    setGuardando(true)
    setError('')
    try {
      await api.asistenteConfirmarMovimiento({
        cuenta_id: cuentaId,
        descripcion: p.descripcion,
        monto: p.monto,
        tipo: p.tipo,
        categoria: p.categoria,
        fecha: p.fecha,
      })
      onResuelto('confirmado')
    } catch (e) {
      setError(e.message || 'No se pudo guardar. Revisa tu conexión e intenta de nuevo.')
      setGuardando(false)
    }
  }

  if (msg.estado === 'confirmado') {
    return (
      <p className="mt-3 flex items-center gap-1.5 text-xs font-semibold text-accent">
        <Check size={16} /> Movimiento guardado
      </p>
    )
  }
  if (msg.estado === 'cancelado') return <p className="mt-3 text-xs text-ink-soft">Cancelado, no se guardó nada.</p>

  return (
    <div className="mt-3 card-marca-sm bg-paper border border-line p-3" role="group" aria-label="Movimiento propuesto">
      <p className="t-kicker text-ink-soft">{p.tipo === 'income' ? 'Ingreso' : 'Gasto'} propuesto</p>
      <p className="text-2xl t-display mt-1">{formatCOP(p.monto)}</p>
      <p className="text-sm mt-0.5">{p.descripcion}</p>
      <p className="text-xs text-ink-soft mt-0.5">
        {p.categoria} · {String(p.fecha).slice(0, 10)}
      </p>
      <label className="block mt-2.5 text-xs text-ink-soft">
        Cuenta
        <select
          value={cuentaId}
          onChange={(e) => setCuentaId(e.target.value)}
          className="mt-1 w-full rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-sm text-ink"
        >
          <option value="">Elige una cuenta…</option>
          {msg.cuentas.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="alert" className="text-xs text-danger mt-2">{error}</p>}
      <div className="flex gap-2 mt-3">
        <button
          type="button"
          onClick={confirmar}
          disabled={guardando}
          className="flex-1 min-h-11 rounded-xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-50"
        >
          {guardando ? 'Guardando…' : 'Confirmar'}
        </button>
        <button
          type="button"
          onClick={() => onResuelto('cancelado')}
          disabled={guardando}
          className="min-h-11 px-4 rounded-xl border border-line text-sm font-medium"
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}

// Tarjeta de plan: resumen cuantificado + botón para crear la meta.
function TarjetaPlan({ msg, onResuelto }) {
  const c = msg.calculo
  const a = msg.accion
  const [cuentaId, setCuentaId] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function aceptar() {
    setGuardando(true)
    setError('')
    try {
      await api.asistenteConfirmarPlan({
        nombre: a.nombre,
        monto_objetivo: a.monto_objetivo,
        fecha_objetivo: a.fecha_objetivo,
        aporte_mensual: a.aporte_mensual,
        cuenta_origen_id: cuentaId || null,
        descripcion: a.descripcion || '',
      })
      onResuelto('confirmado')
    } catch (e) {
      setError(e.message || 'No se pudo crear el plan. Revisa tu conexión e intenta de nuevo.')
      setGuardando(false)
    }
  }

  if (msg.estado === 'confirmado') {
    return (
      <p className="mt-3 flex items-center gap-1.5 text-xs font-semibold text-accent">
        <Check size={16} /> Meta creada: la verás en Metas
      </p>
    )
  }
  if (msg.estado === 'cancelado') return <p className="mt-3 text-xs text-ink-soft">Plan descartado.</p>

  return (
    <div className="mt-3 card-marca-sm bg-paper border border-line p-3 text-xs space-y-1.5" role="group" aria-label="Plan propuesto">
      {c.extra_mensual !== undefined ? (
        <>
          <Fila k="Deuda total" v={formatCOP(c.deuda_total)} />
          <Fila k="Extra mensual necesario" v={formatCOP(c.extra_mensual)} fuerte />
          <Fila k="Pago total mensual" v={formatCOP(c.pago_total_mensual)} />
          <Fila k="Plazo" v={`${c.meses_objetivo} meses`} />
        </>
      ) : (
        <>
          <Fila k="Objetivo" v={formatCOP(c.objetivo)} />
          <Fila k="Aporte mensual" v={formatCOP(c.aporte_mensual)} fuerte />
          <Fila k="Plazo" v={`${c.meses} meses`} />
        </>
      )}
      <p className={`text-[11px] font-semibold ${c.viable ? 'text-accent' : 'text-ink'}`}>
        {c.viable ? 'Cabe en tu capacidad de ahorro' : 'Supera tu capacidad de ahorro actual'}
      </p>
      <label className="block pt-1 text-ink-soft">
        Aportar automáticamente cada mes desde (opcional)
        <select
          value={cuentaId}
          onChange={(e) => setCuentaId(e.target.value)}
          className="mt-1 w-full rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-sm text-ink"
        >
          <option value="">No, solo crear la meta</option>
          {msg.cuentas.map((cu) => (
            <option key={cu.id} value={cu.id}>
              {cu.nombre}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="alert" className="text-danger">{error}</p>}
      <div className="flex gap-2 pt-1.5">
        <button
          type="button"
          onClick={aceptar}
          disabled={guardando}
          className="flex-1 min-h-11 rounded-xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-50"
        >
          {guardando ? 'Creando…' : 'Aceptar plan'}
        </button>
        <button
          type="button"
          onClick={() => onResuelto('cancelado')}
          disabled={guardando}
          className="min-h-11 px-4 rounded-xl border border-line text-sm font-medium"
        >
          Descartar
        </button>
      </div>
    </div>
  )
}

export default function Asistente() {
  const volver = useVolver('/')
  const [mensajes, setMensajes] = useState([])
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [conCuadri] = useMostrarCuadri()
  const [sugerencias, setSugerencias] = useState({ preguntas: [], oportunidades: [] })
  const fin = useRef(null)

  useEffect(() => {
    api.asistenteSugerencias().then(setSugerencias).catch(() => {})
  }, [])

  useEffect(() => {
    fin.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes])

  // Pregunta que el servidor rechazó por falta de autorización de IA: se reenvía sola al autorizar.
  const [pendiente, setPendiente] = useState('')
  const pendienteRef = useRef('')
  const enviarRef = useRef(null)

  async function enviar(contenido, { reenvio = false } = {}) {
    const limpio = (contenido ?? texto).trim()
    if (!limpio || (enviando && !reenvio)) return
    setTexto('')
    setPendiente('')
    pendienteRef.current = ''
    setMensajes((prev) => [...prev, { rol: 'usuario', texto: limpio }])
    setEnviando(true)
    try {
      const r = await api.asistenteMensaje(limpio)
      setMensajes((prev) => [...prev, { rol: 'asistente', ...r }])
    } catch (e) {
      if (e.codigo === 'consentimiento_requerido') {
        // No es un error de la conversación: se quita la pregunta del chat (así siguen los chips
        // de sugerencias) y se espera la autorización para reenviarla.
        setMensajes((prev) => prev.slice(0, -1))
        pendienteRef.current = limpio
        setPendiente(limpio)
      } else {
        setMensajes((prev) => [...prev, { rol: 'asistente', tipo: 'error', texto: e.message || 'No pude procesar eso ahora.' }])
      }
    } finally {
      setEnviando(false)
    }
  }
  enviarRef.current = enviar

  useEffect(() => {
    function alResolver(e) {
      const pregunta = pendienteRef.current
      if (!pregunta) return
      if (e.detail?.aceptado) {
        e.detail.atendido = true
        enviarRef.current(pregunta, { reenvio: true })
      } else {
        // dijo "Ahora no": la pregunta vuelve al cuadro de texto para no perderla
        pendienteRef.current = ''
        setPendiente('')
        setTexto(pregunta)
      }
    }
    window.addEventListener(EVENTO_RESUELTO, alResolver)
    return () => window.removeEventListener(EVENTO_RESUELTO, alResolver)
  }, [])

  function resolver(indice, estado) {
    setMensajes((prev) => prev.map((m, i) => (i === indice ? { ...m, estado } : m)))
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 shrink-0 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        {conCuadri ? <Cuadri pose={enviando ? 'hablando' : 'feliz'} size={44} /> : <Isotipo size={26} />}
        <div>
          <h1 className="t-title text-lg leading-tight">CuadraMe AI</h1>
          <p className="text-[11px] text-ink-soft">Conoce tus cifras · te pide permiso antes de guardar</p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 pb-3 space-y-3" aria-live="polite">
        {mensajes.length === 0 && (
          <div className="pt-3">
            {conCuadri && <p className="text-sm font-medium mb-1">{FRASES.asistente[0]}</p>}
            <p className="text-sm text-ink-soft">
              Pregúntame por tu plata, registra un gasto escribiéndolo (<em>«gasté 18.000 en almuerzo con Nequi»</em>) o
              simula una decisión (<em>«¿puedo comprar un celular de 4 millones?»</em>).
            </p>
            {/* Primero lo que se puede hacer con un toque; los avisos van después y son pocos (una pared de alertas espanta) */}
            <div className="mt-4 flex flex-wrap gap-2" aria-label="Preguntas sugeridas">
              {sugerencias.preguntas.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => enviar(p.texto)}
                  className="min-h-11 px-3.5 rounded-full border border-line bg-paper-raised text-xs font-medium text-ink text-left"
                >
                  {p.texto}
                </button>
              ))}
            </div>
            {sugerencias.oportunidades.length > 0 && (
              <section className="mt-5 space-y-2" aria-label="Lo que noté">
                <p className="t-kicker text-ink-soft">Lo que noté</p>
                {sugerencias.oportunidades.slice(0, 2).map((o, i) => (
                  <div key={i} className="card-marca-sm bg-paper-raised border border-line p-3 flex gap-2.5">
                    {o.tipo === 'recurrentes' ? (
                      <Sparkles size={16} className="text-accent shrink-0 mt-0.5" />
                    ) : (
                      <AlertTriangle size={16} className="text-ink shrink-0 mt-0.5" />
                    )}
                    <div>
                      <p className="text-sm font-semibold">{o.titulo}</p>
                      <p className="text-xs text-ink-soft mt-0.5">{o.detalle}</p>
                    </div>
                  </div>
                ))}
              </section>
            )}
          </div>
        )}

        {mensajes.map((m, i) =>
          m.rol === 'usuario' ? (
            <div key={i} className="max-w-[85%] self-end ml-auto rounded-2xl bg-ink text-paper px-3.5 py-2.5 text-sm">
              {m.texto}
            </div>
          ) : (
            <div key={i} className="max-w-[96%] flex items-start gap-2">
            {/* Avatar de Cuadri: quieto salvo en la última respuesta; preocupado si falló */}
            <Cuadri pose={m.tipo === 'error' ? 'preocupado' : 'feliz'} size={34} animar={i === mensajes.length - 1} className="mt-1" />
            <div
              className={`min-w-0 flex-1 rounded-2xl border px-3.5 py-3 text-sm ${
                m.tipo === 'error' ? 'bg-danger-soft border-danger/30 text-danger' : 'bg-paper-raised border-line'
              }`}
            >
              <p className="whitespace-pre-line">{m.texto}</p>
              {m.monedas_sin_tasa?.length > 0 && <AvisoSinTasa monedas={m.monedas_sin_tasa} base={m.moneda_base} className="mt-2" />}
              {m.tipo === 'simulacion' && <TarjetaSimulacion c={m.calculo} />}
              {m.tipo === 'propuesta_movimiento' && <TarjetaPropuesta msg={m} onResuelto={(e) => resolver(i, e)} />}
              {m.tipo === 'plan' && <TarjetaPlan msg={m} onResuelto={(e) => resolver(i, e)} />}
              {m.sugerencias?.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2.5">
                  {m.sugerencias.map((q) => (
                    <button key={q} type="button" onClick={() => enviar(q)} className="text-xs rounded-full border border-line bg-paper px-3 py-1.5 min-h-[34px]">
                      {q}
                    </button>
                  ))}
                </div>
              )}
              <Fuentes fuentes={m.fuentes} />
            </div>
            </div>
          )
        )}
        {pendiente && !enviando && (
          <p role="status" className="text-xs text-ink-soft">
            Para responder «{pendiente}» necesito tu autorización de IA. Al aceptarla la envío sola.
          </p>
        )}
        {enviando && <p className="text-xs text-ink-soft">{conCuadri ? FRASES.asistentePensando[0] : 'Pensando…'}</p>}
        <div ref={fin} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          enviar()
        }}
        className="flex gap-2 px-6 pt-2 pb-3 border-t border-line"
      >
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          maxLength={500}
          aria-label="Mensaje para CuadraMe AI"
          placeholder="Escribe aquí…"
          className="flex-1 rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={enviando || !texto.trim()}
          aria-label="Enviar"
          className="w-12 h-12 shrink-0 rounded-2xl bg-ink text-paper flex items-center justify-center disabled:opacity-50"
        >
          <Send size={16} />
        </button>
      </form>
      <p className="px-6 pb-2 text-[11px] text-ink-soft text-center">
        <X size={16} className="inline -mt-0.5" aria-hidden="true" /> No guardamos tus conversaciones. Nunca escribas claves ni PIN.
      </p>
    </div>
  )
}
