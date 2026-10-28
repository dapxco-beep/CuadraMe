import { textoError } from '../lib/textoError'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PiggyBank, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'
import { useMarcarFuncion, useModoMenu } from '../lib/modoSimple'
import Hoja from './Hoja'
import Icono from './Icono'
import { finDeMes } from './PlanificadorMeta'
import InputMonto from './InputMonto'
import { Campo, CampoMonto, CampoTexto } from './ui'

/**
 * «Nueva meta». Mientras la persona escribe cuánto necesita (y, si quiere, para cuándo), le dice en palabras
 * cuánto apartar al mes y cuándo llegaría, según lo que de verdad le sobra. Tocar una opción la pone como
 * aporte automático. Se usa en Metas, Inicio y Presupuesto.
 */
export default function FormMeta({ onClose, onGuardada }) {
  const { cuentas } = useCuentas()
  const { avisar } = useDialogos() || {}
  const [nombre, setNombre] = useState('')
  const [montoObjetivo, setMontoObjetivo] = useState('')
  const [montoActual, setMontoActual] = useState('')
  const [mes, setMes] = useState('')
  const [ahorroAutomatico, setAhorroAutomatico] = useState(false)
  const [aporteAutomatico, setAporteAutomatico] = useState('')
  const [diaAporte, setDiaAporte] = useState('1')
  const [cuentaOrigenId, setCuentaOrigenId] = useState(cuentas[0]?.id || '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [plan, setPlan] = useState(null)

  // Vista previa del plan: espera a que la persona deje de teclear (no pide en cada tecla).
  useEffect(() => {
    const objetivo = Number(montoObjetivo)
    if (!objetivo || objetivo <= 0) {
      setPlan(null)
      return undefined
    }
    let vigente = true
    const t = setTimeout(async () => {
      try {
        const r = await api.simularMeta({
          monto_objetivo: objetivo,
          monto_actual: Number(montoActual) || 0,
          ...(mes ? { fecha_objetivo: finDeMes(mes) } : {}),
        })
        if (vigente) setPlan(r)
      } catch {
        if (vigente) setPlan(null) // la vista previa es una ayuda: si falla, el formulario sigue igual
      }
    }, 400)
    return () => {
      vigente = false
      clearTimeout(t)
    }
  }, [montoObjetivo, montoActual, mes])

  function usarOpcion(monto) {
    setAhorroAutomatico(true)
    setAporteAutomatico(String(monto))
  }

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a tu meta, por ejemplo «Viaje a Cartagena».')
    if (!montoObjetivo || Number(montoObjetivo) <= 0) return setError('Escribe cuánta plata necesitas en total, solo números. Por ejemplo 5000000.')
    if (ahorroAutomatico && (!aporteAutomatico || Number(aporteAutomatico) <= 0)) {
      return setError('Escribe cuánto quieres apartar cada mes, solo números. Por ejemplo 200000.')
    }

    setGuardando(true)
    try {
      const meta = await api.crearMeta({
        nombre: nombre.trim(),
        monto_objetivo: Number(montoObjetivo),
        monto_actual: Number(montoActual) || 0,
        ...(mes && { fecha_objetivo: finDeMes(mes) }),
        ...(ahorroAutomatico && {
          aporte_automatico: Number(aporteAutomatico),
          dia_aporte: Number(diaAporte) || 1,
          cuenta_origen_id: cuentaOrigenId || null,
        }),
      })
      avisar?.(`Listo: creaste la meta «${nombre.trim()}». Toca «Aportar ahora» cuando separes plata.`, 'ok')
      onGuardada?.(meta)
    } catch (err) {
      setError(textoError(err, 'crear la meta'))
    } finally {
      setGuardando(false)
    }
  }

  const opciones = plan?.opciones || []

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
        className="mb-3"
      />
      <Campo etiqueta="¿Para cuándo la quieres? (opcional)" className="mb-4">
        {(props) => <input {...props} type="month" value={mes} onChange={(e) => setMes(e.target.value)} />}
      </Campo>

      {plan && (
        <div className="rounded-2xl bg-accent-soft p-3.5 mb-4" role="status" aria-live="polite" data-testid="vista-previa-meta">
          {plan.texto_necesario && <p className="text-sm font-semibold">{plan.texto_necesario}</p>}
          {opciones.length > 0 ? (
            <>
              <p className="text-xs text-ink-soft mt-1">
                Según lo que te ha sobrado cada mes ({formatCOP(plan.sobrante_mensual)}), puedes apartar:
              </p>
              <div className="mt-2 grid gap-2">
                {opciones.map((o) => (
                  <button
                    key={o.id}
                    type="button"
                    onClick={() => usarOpcion(o.monto)}
                    aria-pressed={ahorroAutomatico && Number(aporteAutomatico) === o.monto}
                    className="text-left rounded-xl border border-line bg-paper-raised px-3 py-2.5 min-h-11"
                  >
                    <span className="block text-sm font-semibold">
                      {o.nombre}: {formatCOP(o.monto)} al mes
                    </span>
                    <span className="block text-xs text-ink-soft">{o.texto}</span>
                  </button>
                ))}
              </div>
            </>
          ) : (
            plan.aviso_sobrante && <p className="text-xs text-ink-soft mt-1">{plan.aviso_sobrante}</p>
          )}
        </div>
      )}

      <button
        type="button"
        role="switch"
        aria-checked={ahorroAutomatico}
        onClick={() => setAhorroAutomatico((v) => !v)}
        className="w-full flex items-center gap-3 rounded-2xl border border-line bg-paper-raised px-4 py-3.5 mb-3 min-h-11"
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
            Ese día sale de la cuenta elegida y se suma a tu meta. No cuenta como gasto.
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

/**
 * Botón «Crear una meta de ahorro» para Inicio y Presupuesto. Al crear la primera, «Metas» pasa a verse
 * en el menú (modo simple) y se abre la pantalla de metas.
 */
export function BotonCrearMeta({ className = '', texto = 'Crear una meta de ahorro' }) {
  const [abierta, setAbierta] = useState(false)
  const marcar = useMarcarFuncion()
  const navigate = useNavigate()
  return (
    <>
      <button
        type="button"
        onClick={() => setAbierta(true)}
        className={`flex items-center justify-center gap-2 text-sm text-accent font-semibold min-h-11 ${className}`}
      >
        <Icono icono={PiggyBank} tam="sm" /> {texto}
      </button>
      {abierta && (
        <FormMeta
          onClose={() => setAbierta(false)}
          onGuardada={() => {
            setAbierta(false)
            marcar('/metas')
            navigate('/metas')
          }}
        />
      )}
    </>
  )
}

/** Ofrece crear la primera meta solo a quien aún no usa «Metas» (desaparece al crearla). */
export function OfrecerPrimeraMeta({ className = '' }) {
  const { enUso } = useModoMenu()
  if (enUso.includes('/metas')) return null
  return (
    <div className={className} data-testid="ofrecer-meta">
      <BotonCrearMeta />
    </div>
  )
}
