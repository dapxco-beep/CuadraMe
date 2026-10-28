import { textoError } from '../lib/textoError'
import { useEffect, useRef, useState } from 'react'
import { EsqueletoLista } from '../components/Esqueletos'
import { EstadoVacio } from '../brand/Marca'
import { useVolver } from '../lib/useVolver'
import { useEstadoLista } from '../lib/useEstadoLista'
import { ArrowLeft, Lightbulb, PartyPopper, Plus, Repeat, X, PiggyBank, Sparkles, TrendingDown, TrendingUp, Check } from 'lucide-react'
import Icono from '../components/Icono'
import PlanificadorMeta from '../components/PlanificadorMeta'
import FormMeta from '../components/FormMeta'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import Hoja from '../components/Hoja'
import { useDialogos } from '../lib/DialogosContext'
import BarraProgreso from '../components/BarraProgreso'
import CelebracionCuadri from '../brand/CelebracionCuadri'
import { FRASES, yaCelebrado } from '../lib/cuadri'
import InputMonto from '../components/InputMonto'
import EnlacesRelacionados from '../components/EnlacesRelacionados'

// Cuánto se propone aportar «ahora»: la opción sugerida según lo que te sobra; si no hay, lo que pide
// llegar a tiempo; si no, el aporte automático que ya tiene la meta.
export function montoSugerido(plan, meta) {
  const sugerida = plan?.opciones?.find((o) => o.id === plan.opcion_sugerida)
  return sugerida?.monto || plan?.aporte_necesario_mes || meta?.aporte_automatico || ''
}

const RITMO = {
  adelantado: { icono: TrendingUp, clase: 'text-accent' },
  al_dia: { icono: Check, clase: 'text-accent' },
  atrasado: { icono: TrendingDown, clase: 'text-gold' },
  vencida: { icono: TrendingDown, clase: 'text-danger' },
}

export default function Metas() {
  const volver = useVolver('/perfil')
  const [metas, setMetas] = useState([])
  const [planes, setPlanes] = useState({})
  const [consejos, setConsejos] = useState([])
  const [cargando, setCargando] = useState(true)
  const raiz = useRef(null)
  const celebrable = useRef(null)
  useEstadoLista('/metas', { contenedorRef: raiz, listo: !cargando }) // al volver, misma posición
  const [mostrarForm, setMostrarForm] = useState(false)
  const [aportando, setAportando] = useState(null) // { meta, monto }
  const [planeando, setPlaneando] = useState(false)
  const [error, setError] = useState('')

  async function cargar() {
    setCargando(true)
    setError('')
    try {
      setMetas(await api.metas())
    } catch (err) {
      setError(err.message || 'No pudimos cargar tus metas. Revisa tu conexión y toca «Reintentar».')
    }
    setCargando(false)
    // El plan y los consejos son una ayuda: si fallan, las metas se ven igual.
    api.metasSugerencias?.().then((r) => setPlanes(r?.metas || {})).catch(() => {})
    api.consejos?.().then((r) => setConsejos(r?.consejos || [])).catch(() => {})
  }

  useEffect(() => {
    cargar()
  }, [])

  return (
    <div ref={raiz} className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={volver}
            className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
           aria-label="Volver">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-semibold">Metas de ahorro</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPlaneando(true)}
            className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
            aria-label="Calcular cuánto ahorrar por mes para una meta">
            <Sparkles size={20} className="text-accent" />
          </button>
          <button
            onClick={() => setMostrarForm(true)}
            className="w-11 h-11 rounded-full bg-accent text-paper-raised flex items-center justify-center"
           aria-label="Crear una meta">
            <Plus size={20} />
          </button>
        </div>
      </header>

      {/* Cuadri celebra una meta cumplida (una sola vez por meta, breve y descartable) */}
      {!cargando && (() => {
        // se fija la primera vez: al marcarse como celebrada no debe saltar a otra meta y desmontar el aviso
        if (!celebrable.current) celebrable.current = metas.find((m) => m.completada && !yaCelebrado(`meta-${m.id}`)) || null
        const lograda = celebrable.current
        return lograda ? <CelebracionCuadri id={`meta-${lograda.id}`} titulo={`¡Lograste «${lograda.nombre}»!`} texto={FRASES.celebraMeta[0]} /> : null
      })()}

      {cargando ? (
        <EsqueletoLista filas={3} className="mx-5 mt-6" etiqueta="Cargando tus metas" />
      ) : error ? (
        <div className="mx-5 mt-6 rounded-2xl bg-danger-soft p-6 text-center">
          <p className="text-sm text-danger mb-3">{error}</p>
          <button onClick={cargar} className="text-sm font-semibold text-danger underline">
            Reintentar
          </button>
        </div>
      ) : metas.length === 0 ? (
        <EstadoVacio icono={PiggyBank} titulo="Aún no tienes metas de ahorro" texto="Una meta es algo que quieres comprar o lograr, como un viaje. Dile cuánta plata necesitas y te decimos cuánto apartar al mes." className="mx-5 mt-6">
          <button onClick={() => setMostrarForm(true)} className="btn btn-primario btn-sm mt-4">Crear mi primera meta</button>
        </EstadoVacio>
      ) : (
        <div className="mx-5 mt-4 space-y-3 max-w-2xl md:mx-auto">
          {metas.map((m, i) => (
            <TarjetaMeta
              key={m.id}
              meta={m}
              plan={planes[m.id]}
              consejo={consejos.find((c) => c.tipo === 'meta_sin_aporte' && c.meta_id === m.id)}
              indice={i}
              onAportar={(monto) => setAportando({ meta: m, monto })}
            />
          ))}
        </div>
      )}

      {!cargando && !error && metas.length > 0 && (
        <div className="max-w-2xl md:mx-auto">
          <EnlacesRelacionados enlaces={[
            { a: '/cuentas', texto: 'Mis cuentas', apoyo: 'Mira dónde tienes la plata para tus metas' },
            { a: '/recurrentes', texto: 'Pagos fijos', apoyo: 'Lo que ya tienes comprometido cada mes' },
            { a: '/presupuesto', texto: 'Mi presupuesto', apoyo: 'Cuánto te sobra para ahorrar' },
          ]} />
        </div>
      )}

      {planeando && (
        <PlanificadorMeta
          onClose={() => setPlaneando(false)}
          onCreada={() => {
            setPlaneando(false)
            cargar()
          }}
        />
      )}

      {mostrarForm && (
        <FormMeta
          onClose={() => setMostrarForm(false)}
          onGuardada={() => {
            setMostrarForm(false)
            cargar()
          }}
        />
      )}

      {aportando && (
        <FormAporte
          meta={aportando.meta}
          montoInicial={aportando.monto}
          onClose={() => setAportando(null)}
          onAportado={() => {
            setAportando(null)
            cargar()
          }}
        />
      )}
    </div>
  )
}

function TarjetaMeta({ meta: m, plan, consejo, indice, onAportar }) {
  const [verOpciones, setVerOpciones] = useState(false)
  const ritmo = plan?.estado_ritmo && RITMO[plan.estado_ritmo]
  const opciones = plan?.opciones || []
  const sugerida = opciones.find((o) => o.id === plan?.opcion_sugerida)
  return (
    <div className="rounded-2xl bg-paper-raised border border-line p-4 stagger-item" style={{ '--stagger-i': indice }} data-testid={`meta-${m.id}`}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-semibold">{m.nombre}</p>
        <p className="text-xs text-ink-soft">{m.progreso_pct}%</p>
      </div>
      <BarraProgreso pct={m.progreso_pct} label={`Progreso de ${m.nombre}`} className="h-2 rounded-full bg-line overflow-hidden mb-2" />
      <div className="flex items-center justify-between text-xs text-ink-soft mb-3">
        <span>{formatCOP(m.monto_actual)}</span>
        <span>{formatCOP(m.monto_objetivo)}</span>
      </div>

      {!m.completada && plan?.frase_ritmo && ritmo && (
        <p className={`text-sm font-semibold flex items-center gap-1.5 mb-2 ${ritmo.clase}`} data-testid="ritmo-meta">
          <Icono icono={ritmo.icono} tam="sm" /> {plan.frase_ritmo}
        </p>
      )}

      {!m.completada && (
        <div className="space-y-1.5 mb-3" data-testid="plan-de-la-meta">
          {plan?.texto_necesario && <p className="text-sm">{plan.texto_necesario}.</p>}
          {sugerida && <p className="text-sm font-medium">{sugerida.texto}.</p>}
          {!sugerida && plan?.aviso_sobrante && <p className="text-xs text-ink-soft">{plan.aviso_sobrante}</p>}
          {!plan?.texto_necesario && plan?.estado_ritmo === 'sin_fecha' && (
            <p className="text-xs text-ink-soft">Ponle una fecha a esta meta y te decimos cuánto apartar al mes.</p>
          )}
          {m.eta_meses && !sugerida && (
            <p className="text-xs text-ink-soft">
              Si sigues así, la alcanzas en ~{m.eta_meses} {m.eta_meses === 1 ? 'mes' : 'meses'}
            </p>
          )}
          {opciones.length > 1 && (
            <button
              type="button"
              onClick={() => setVerOpciones((v) => !v)}
              aria-expanded={verOpciones}
              className="text-xs font-semibold text-accent min-h-11 pr-2"
            >
              {verOpciones ? 'Ocultar otras opciones' : 'Ver otras opciones'}
            </button>
          )}
          {verOpciones && (
            <div className="grid gap-2" role="group" aria-label={`Opciones de aporte para ${m.nombre}`}>
              {opciones.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  onClick={() => onAportar(o.monto)}
                  className="text-left rounded-xl border border-line px-3 py-2.5 min-h-11"
                >
                  <span className="block text-sm font-semibold">{o.nombre}: {formatCOP(o.monto)} al mes</span>
                  <span className="block text-xs text-ink-soft">{o.texto}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {m.aporte_automatico && !m.completada && (
        <p className="text-xs text-accent flex items-center gap-1 mb-3">
          <Repeat size={16} /> {formatCOP(m.aporte_automatico)} automático el día {m.dia_aporte}
        </p>
      )}

      {consejo && !m.completada && (
        <div className="rounded-xl bg-accent-soft p-3 mb-3 flex gap-2" role="note" data-testid="consejo-meta">
          <Icono icono={Lightbulb} tam="sm" className="text-accent shrink-0 mt-0.5" />
          <p className="text-xs">{consejo.texto}</p>
        </div>
      )}

      {m.completada ? (
        <p className="text-sm font-semibold text-accent flex items-center gap-1.5"><Icono icono={PartyPopper} tam="sm" /> ¡Meta completada!</p>
      ) : (
        <button
          onClick={() => onAportar(montoSugerido(plan, m))}
          className="w-full bg-ink text-paper font-semibold rounded-xl py-2.5 min-h-11 text-sm"
        >
          Aportar ahora
        </button>
      )}
    </div>
  )
}

function FormAporte({ meta, montoInicial, onClose, onAportado }) {
  const { cuentas } = useCuentas()
  const { avisar } = useDialogos() || {}
  const [monto, setMonto] = useState(montoInicial ? String(montoInicial) : '')
  // La plata sale de la cuenta de origen de la meta si la tiene; si no, de «ya la tenía aparte».
  const [cuentaId, setCuentaId] = useState(meta.cuenta_origen_id && cuentas.some((c) => c.id === meta.cuenta_origen_id) ? meta.cuenta_origen_id : '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!monto || Number(monto) <= 0) return setError('Escribe cuánto vas a aportar, solo números. Por ejemplo 100000.')

    setGuardando(true)
    try {
      const r = await api.aportarMeta(meta.id, Number(monto), cuentaId || undefined)
      avisar?.(
        r?.completada
          ? `¡Lo lograste! Sumaste ${formatCOP(Number(monto))} y «${meta.nombre}» está completa.`
          : `Listo: sumaste ${formatCOP(Number(monto))} a «${meta.nombre}».`,
        'ok'
      )
      onAportado(r)
    } catch (err) {
      setError(textoError(err, 'registrar el aporte'))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Aportar a "{meta.nombre}"</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      <InputMonto entero
        value={monto}
        onValor={setMonto}
        placeholder="¿Cuánto aportas? Ej. 100000"
        aria-label="Cuánto aportas"
        autoFocus
        className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
      />

      {cuentas.length > 0 && (
        <>
          <select
            value={cuentaId}
            onChange={(e) => setCuentaId(e.target.value)}
            aria-label="De dónde sale la plata"
            className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm mb-1"
          >
            <option value="">Ya la tenía aparte: no descontar de mis cuentas</option>
            {cuentas.map((c) => (
              <option key={c.id} value={c.id}>Descontar de {c.nombre}</option>
            ))}
          </select>
          <p className="text-xs text-ink-soft mb-4">
            {cuentaId
              ? 'Baja del saldo de esa cuenta y queda en tus movimientos como traslado a tu meta. No cuenta como gasto.'
              : 'Solo suma a tu meta: no cambia el saldo de tus cuentas.'}
          </p>
        </>
      )}

      {error && <p role="alert" className="text-sm text-danger mb-3">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
      >
        {guardando ? 'Guardando...' : 'Aportar ahora'}
      </button>
    </Hoja>
  )
}
