import { useEffect, useRef, useState } from 'react'
import { EsqueletoLista } from '../components/Esqueletos'
import { EstadoVacio } from '../brand/Marca'
import { useVolver } from '../lib/useVolver'
import { useEstadoLista } from '../lib/useEstadoLista'
import { ArrowLeft, PartyPopper, Plus, Repeat, X, PiggyBank, Sparkles } from 'lucide-react'
import Icono from '../components/Icono'
import PlanificadorMeta from '../components/PlanificadorMeta'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import Hoja from '../components/Hoja'
import { CampoTexto, CampoMonto } from '../components/ui'
import { useDialogos } from '../lib/DialogosContext'
import BarraProgreso from '../components/BarraProgreso'
import CelebracionCuadri from '../brand/CelebracionCuadri'
import { FRASES, yaCelebrado } from '../lib/cuadri'
import InputMonto from '../components/InputMonto'

export default function Metas() {
  const volver = useVolver('/perfil')
  const [metas, setMetas] = useState([])
  const [cargando, setCargando] = useState(true)
  const raiz = useRef(null)
  const celebrable = useRef(null)
  useEstadoLista('/metas', { contenedorRef: raiz, listo: !cargando }) // al volver, misma posición
  const [mostrarForm, setMostrarForm] = useState(false)
  const [aportando, setAportando] = useState(null)
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
        <EstadoVacio icono={PiggyBank} titulo="Aún no tienes metas de ahorro" texto="Una meta es algo que quieres comprar o lograr, como un viaje. Dile cuánto necesitas y vas viendo cómo avanzas." className="mx-5 mt-6">
          <button onClick={() => setMostrarForm(true)} className="btn btn-primario btn-sm mt-4">Crear mi primera meta</button>
        </EstadoVacio>
      ) : (
        <div className="mx-5 mt-4 space-y-3">
          {metas.map((m, i) => (
            <div key={m.id} className="rounded-2xl bg-paper-raised border border-line p-4 stagger-item" style={{ '--stagger-i': i }}>
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-semibold">{m.nombre}</p>
                <p className="text-xs text-ink-soft">{m.progreso_pct}%</p>
              </div>
              <BarraProgreso pct={m.progreso_pct} label={`Progreso de ${m.nombre}`} className="h-2 rounded-full bg-line overflow-hidden mb-2" />
              <div className="flex items-center justify-between text-xs text-ink-soft mb-3">
                <span>{formatCOP(m.monto_actual)}</span>
                <span>{formatCOP(m.monto_objetivo)}</span>
              </div>
              {m.eta_meses && !m.completada && (
                <p className="text-xs text-ink-soft mb-1.5">
                  A tu ritmo actual, la alcanzas en ~{m.eta_meses} {m.eta_meses === 1 ? 'mes' : 'meses'}
                </p>
              )}
              {m.aporte_automatico && !m.completada && (
                <p className="text-xs text-accent flex items-center gap-1 mb-3">
                  <Repeat size={16} /> {formatCOP(m.aporte_automatico)} automático el día {m.dia_aporte}
                </p>
              )}
              {m.completada ? (
                <p className="text-sm font-semibold text-accent flex items-center gap-1.5"><Icono icono={PartyPopper} tam="sm" /> ¡Meta completada!</p>
              ) : (
                <button
                  onClick={() => setAportando(m)}
                  className="w-full bg-ink text-paper font-semibold rounded-xl py-2.5 text-sm"
                >
                  Aportar
                </button>
              )}
            </div>
          ))}
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
          meta={aportando}
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

function FormMeta({ onClose, onGuardada }) {
  const { cuentas } = useCuentas()
  const { avisar } = useDialogos() || {}
  const [nombre, setNombre] = useState('')
  const [montoObjetivo, setMontoObjetivo] = useState('')
  const [montoActual, setMontoActual] = useState('')
  const [ahorroAutomatico, setAhorroAutomatico] = useState(false)
  const [aporteAutomatico, setAporteAutomatico] = useState('')
  const [diaAporte, setDiaAporte] = useState('1')
  const [cuentaOrigenId, setCuentaOrigenId] = useState(cuentas[0]?.id || '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a tu meta, por ejemplo «Viaje a Cartagena».')
    if (!montoObjetivo || Number(montoObjetivo) <= 0) return setError('Escribe cuánta plata necesitas en total, solo números. Por ejemplo 5000000.')
    if (ahorroAutomatico && (!aporteAutomatico || Number(aporteAutomatico) <= 0)) {
      return setError('Escribe cuánto quieres apartar cada mes, solo números. Por ejemplo 200000.')
    }

    setGuardando(true)
    try {
      await api.crearMeta({
        nombre: nombre.trim(),
        monto_objetivo: Number(montoObjetivo),
        monto_actual: Number(montoActual) || 0,
        ...(ahorroAutomatico && {
          aporte_automatico: Number(aporteAutomatico),
          dia_aporte: Number(diaAporte) || 1,
          cuenta_origen_id: cuentaOrigenId || null,
        }),
      })
      avisar?.(`Listo: creaste la meta «${nombre.trim()}». Toca «Aportar» cuando separes plata.`, 'ok')
      onGuardada()
    } catch (err) {
      setError(err.message || 'No pudimos crear la meta. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Nueva meta</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      <CampoTexto
        etiqueta="¿Qué quieres lograr?"
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
        placeholder="Ej. Viaje a Cartagena"
        className="mb-3"
      />
      <CampoMonto
        entero
        etiqueta="¿Cuánta plata necesitas en total?"
        value={montoObjetivo}
        onValor={setMontoObjetivo}
        placeholder="Ej. 5000000"
        className="mb-3"
      />
      <CampoMonto
        entero
        etiqueta="¿Cuánto llevas ahorrado? (opcional)"
        value={montoActual}
        onValor={setMontoActual}
        placeholder="Si empiezas de cero, déjalo vacío"
        className="mb-4"
      />

      <button
        type="button"
        role="switch"
        aria-checked={ahorroAutomatico}
        onClick={() => setAhorroAutomatico((v) => !v)}
        className="w-full flex items-center gap-3 rounded-2xl border border-line bg-paper-raised px-4 py-3.5 mb-3"
      >
        <span
          className={`w-5 h-5 rounded-md border flex items-center justify-center shrink-0 ${
            ahorroAutomatico ? 'bg-accent border-accent' : 'border-line'
          }`}
        >
          {ahorroAutomatico && <span className="w-2 h-2 rounded-sm bg-white" />}
        </span>
        <span className="text-sm text-left flex-1">Separar plata sola cada mes</span>
      </button>

      {ahorroAutomatico && (
        <div className="rounded-2xl bg-accent-soft p-3 mb-4 space-y-3">
          <InputMonto entero
            value={aporteAutomatico}
            onValor={setAporteAutomatico}
            placeholder="Cuánto separar cada mes"
            aria-label="Cuánto separar cada mes"
            className="w-full rounded-xl border border-line bg-paper px-3.5 py-3 text-sm outline-none focus:border-accent"
          />
          <div className="flex gap-2">
            <input
              value={diaAporte}
              onChange={(e) => setDiaAporte(e.target.value.replace(/\D/g, '').slice(0, 2))}
              inputMode="numeric"
              placeholder="Día del mes (1-31)"
              aria-label="Día del mes en que se separa"
              className="flex-1 rounded-xl border border-line bg-paper px-3.5 py-3 text-sm outline-none focus:border-accent"
            />
            {cuentas.length > 0 && (
              <select
                value={cuentaOrigenId}
                onChange={(e) => setCuentaOrigenId(e.target.value)}
                aria-label="Cuenta de la que sale la plata"
                className="flex-1 rounded-xl border border-line bg-paper px-3.5 py-3 text-sm"
              >
                {cuentas.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre}</option>
                ))}
              </select>
            )}
          </div>
          <p className="text-xs text-ink-soft">
            Ese día sale de la cuenta elegida y se suma a tu meta.
          </p>
        </div>
      )}

      {error && <p role="alert" className="text-sm text-danger mb-3">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
      >
        {guardando ? 'Guardando...' : 'Crear meta'}
      </button>
    </Hoja>
  )
}

function FormAporte({ meta, onClose, onAportado }) {
  const { cuentas } = useCuentas()
  const { avisar } = useDialogos() || {}
  const [monto, setMonto] = useState('')
  const [cuentaId, setCuentaId] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!monto || Number(monto) <= 0) return setError('Escribe cuánto vas a aportar, solo números. Por ejemplo 100000.')

    setGuardando(true)
    try {
      await api.aportarMeta(meta.id, Number(monto), cuentaId || undefined)
      avisar?.(`Listo: sumaste ${formatCOP(Number(monto))} a «${meta.nombre}».`, 'ok')
      onAportado()
    } catch (err) {
      setError(err.message || 'No pudimos registrar el aporte. Revisa tu conexión e intenta de nuevo.')
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
            Si eliges una cuenta, ese valor baja de su saldo.
          </p>
        </>
      )}

      {error && <p role="alert" className="text-sm text-danger mb-3">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
      >
        {guardando ? 'Guardando...' : 'Aportar'}
      </button>
    </Hoja>
  )
}
