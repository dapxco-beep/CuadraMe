import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeftRight, PiggyBank, Plus, Sprout, X } from 'lucide-react'
import { api } from '../lib/api'
import { AVISO_EDUCATIVO } from '../lib/avisoEducativo'
import { useBloqueo } from '../lib/BloqueoContext'
import { useDialogos } from '../lib/DialogosContext'
import { avisarCambioRendimientos, fechaCorta, formatTasa, leerTasa, useRendimientos } from '../lib/rendimientos'
import Ayudita from './Ayudita'
import Hoja from './Hoja'
import Icono from './Icono'
import { Boton, CampoMonto, CampoTexto } from './ui'

// «Tu plata trabajando»: cajitas/bolsillos y rendimiento ESTIMADO.
// Una cajita es una PARTE del saldo de la cuenta (no plata extra): crearla o mover plata hacia/desde
// ella no cambia el saldo, no es gasto ni ingreso y no se suma dos veces en Patrimonio.

const PESOS = (fmt, n, moneda) => fmt(Math.round(n || 0), moneda)
const montoDe = (v) => Number(String(v ?? '').replace(',', '.')) || 0

const AVISO_ESTIMACION = 'Es una estimación con la tasa que anotaste. Lo que tu banco te pague de verdad puede variar.'

/** Una línea por cuenta de ahorros en «Tus cuentas»: «Rinde 9 % E.A. · ganó ~$X este mes» + «Agregar una cajita». */
export function RendimientoCuenta({ cuentaId }) {
  const { fmt } = useBloqueo()
  const { datos } = useRendimientos()
  const [hoja, setHoja] = useState(null) // 'cajita' | 'tasa'
  const fila = datos?.cuentas?.find((c) => c.cuenta_id === cuentaId)
  if (!fila) return null
  const est = fila.estimado
  return (
    <div className="mt-1.5 px-1" data-testid="rendimiento-cuenta">
      <p className="t-apoyo">
        {est ? (
          <>
            Rinde {formatTasa(fila.tasa_principal)} E.A. <Ayudita termino="ea" /> · ganó ~{PESOS(fmt, est.mes_corrido, fila.moneda)} este mes
            <span className="text-ink-soft"> (estimado)</span>
          </>
        ) : (
          'No sabemos cuánto rinde esta cuenta.'
        )}
      </p>
      <div className="flex flex-wrap gap-x-4">
        <button type="button" onClick={() => setHoja('tasa')} className="text-sm text-accent font-medium min-h-11 inline-flex items-center">
          {fila.tasa_principal == null ? 'Anotar cuánto rinde' : 'Cambiar la tasa'}
        </button>
        <button type="button" onClick={() => setHoja('cajita')} className="text-sm text-accent font-medium min-h-11 inline-flex items-center gap-1">
          <Icono icono={Plus} tam="sm" /> Agregar una cajita
        </button>
      </div>
      {hoja === 'cajita' && <HojaCajita cuentaId={cuentaId} moneda={fila.moneda} principal={fila.principal} onCerrar={() => setHoja(null)} />}
      {hoja === 'tasa' && <HojaTasaCuenta cuentaId={cuentaId} actual={fila.tasa_principal} onCerrar={() => setHoja(null)} />}
    </div>
  )
}

/** En el detalle de una cuenta de ahorros: saldo principal, cajitas y «Mover plata». */
export function CajitasDeCuenta({ cuentaId }) {
  const { fmt } = useBloqueo()
  const { datos } = useRendimientos()
  const [hoja, setHoja] = useState(null) // { tipo: 'cajita' } | { tipo: 'mover', cajita }
  const fila = datos?.cuentas?.find((c) => c.cuenta_id === cuentaId)
  if (!fila) return null
  return (
    <section className="mt-4" aria-label="Cajitas de esta cuenta" data-testid="cajitas-cuenta">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Cajitas</h3>
        <button type="button" onClick={() => setHoja({ tipo: 'cajita' })} className="text-sm text-accent font-medium min-h-11 inline-flex items-center gap-1">
          <Icono icono={Plus} tam="sm" /> Agregar una cajita
        </button>
      </div>
      <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line">
        <div className="flex items-center gap-3 px-4 py-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium">Saldo principal</p>
            <p className="text-xs text-ink-soft">{fila.tasa_principal == null ? 'Sin tasa anotada' : `${formatTasa(fila.tasa_principal)} E.A.`}</p>
          </div>
          <span className="text-sm font-semibold t-cifra">{PESOS(fmt, fila.principal, fila.moneda)}</span>
        </div>
        {fila.cajitas.map((k) => (
          <div key={k.id} className="flex items-center gap-3 px-4 py-3">
            <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
              <Icono icono={PiggyBank} tam="md" />
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{k.nombre}</p>
              <p className="text-xs text-ink-soft">
                {k.tasa_ea == null ? 'Sin tasa anotada' : `${formatTasa(k.tasa_ea)} E.A. · tasa del ${fechaCorta(k.tasa_fecha)}`}
              </p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-sm font-semibold t-cifra">{PESOS(fmt, k.saldo, fila.moneda)}</p>
              <button type="button" onClick={() => setHoja({ tipo: 'mover', cajita: k })} className="text-xs text-accent font-medium min-h-11 inline-flex items-center gap-1">
                <Icono icono={ArrowLeftRight} tam="sm" /> Mover plata
              </button>
            </div>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-ink-soft mt-1.5">
        Las cajitas son parte del saldo de la cuenta, no plata extra. Moverla entre el saldo principal y una cajita no es un gasto ni un ingreso.
      </p>
      {fila.descuadre && (
        <p role="status" className="text-xs text-danger mt-1">
          Tus cajitas suman más que el saldo de la cuenta. Revisa los valores para que cuadren con tu banco.
        </p>
      )}
      {hoja?.tipo === 'cajita' && <HojaCajita cuentaId={cuentaId} moneda={fila.moneda} principal={fila.principal} onCerrar={() => setHoja(null)} />}
      {hoja?.tipo === 'mover' && <HojaMover cajita={hoja.cajita} moneda={fila.moneda} principal={fila.principal} onCerrar={() => setHoja(null)} />}
    </section>
  )
}

function Encabezado({ titulo, onCerrar }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-lg font-semibold">{titulo}</h2>
      <button type="button" onClick={onCerrar} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
        <Icono icono={X} tam="sm" />
      </button>
    </div>
  )
}

function HojaCajita({ cuentaId, moneda, principal, onCerrar }) {
  const { fmt } = useBloqueo()
  const { avisar } = useDialogos() || {}
  const [nombre, setNombre] = useState('')
  const [saldo, setSaldo] = useState('')
  const [tasa, setTasa] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function guardar() {
    setError('')
    const t = leerTasa(tasa)
    if (!nombre.trim()) return setError('Ponle un nombre a la cajita, por ejemplo «Viaje».')
    if (Number.isNaN(t)) return setError('Escribe la tasa como un número, por ejemplo 9,5.')
    if (montoDe(saldo) > principal + 0.5) return setError(`En el saldo principal solo hay ${PESOS(fmt, principal, moneda)} para apartar.`)
    setGuardando(true)
    try {
      await api.crearCajita({ cuenta_id: cuentaId, nombre: nombre.trim(), saldo: montoDe(saldo), tasa_ea: t })
      avisar?.(`Listo: creamos la cajita «${nombre.trim()}».`, 'ok')
      avisarCambioRendimientos()
      onCerrar()
    } catch (err) {
      setError(err.message || 'No pudimos crear la cajita. Revisa tu conexión e intenta de nuevo.')
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onCerrar} ariaLabel="Agregar una cajita" capa="z-[60]" historial={false}>
      <Encabezado titulo="Agregar una cajita" onCerrar={onCerrar} />
      <p className="t-apoyo mb-3">
        Una cajita (o bolsillo) es un apartado dentro de tu cuenta. La plata sigue siendo tuya y sigue sumando al saldo de la cuenta. <Ayudita termino="cajita" />
      </p>
      <div className="space-y-3">
        <CampoTexto etiqueta="Nombre de la cajita" value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={40} placeholder="Ej. Viaje, Emergencias" />
        <CampoMonto etiqueta="¿Cuánta plata hay en ella?" value={saldo} onValor={setSaldo} entero ayuda={`Puedes apartar hasta ${PESOS(fmt, principal, moneda)} del saldo principal.`} />
        <CampoTexto
          etiqueta="¿Cuánto rinde? (tasa E.A., opcional)"
          value={tasa}
          onChange={(e) => setTasa(e.target.value)}
          inputMode="decimal"
          placeholder="Ej. 9,5"
          ayuda="Míralo en la app de tu banco. Si no lo sabes, déjalo vacío."
        />
      </div>
      <p className="text-xs text-ink-soft mt-2">
        Tasa efectiva anual (E.A.) <Ayudita termino="ea" />
      </p>
      {error && <p role="alert" className="text-sm text-danger mt-3">{error}</p>}
      <div className="mt-4">
        <Boton bloque onClick={guardar} cargando={guardando}>
          {guardando ? 'Guardando...' : 'Crear cajita'}
        </Boton>
      </div>
    </Hoja>
  )
}

function HojaMover({ cajita, moneda, principal, onCerrar }) {
  const { fmt } = useBloqueo()
  const { avisar, confirmar } = useDialogos() || {}
  const [sentido, setSentido] = useState('entrar')
  const [monto, setMonto] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const tope = sentido === 'entrar' ? principal : cajita.saldo

  async function mover() {
    setError('')
    const m = montoDe(monto)
    if (m <= 0) return setError('Escribe cuánta plata quieres mover.')
    if (m > tope + 0.5) {
      return setError(sentido === 'entrar' ? `En el saldo principal solo hay ${PESOS(fmt, principal, moneda)}.` : `La cajita solo tiene ${PESOS(fmt, cajita.saldo, moneda)}.`)
    }
    setGuardando(true)
    try {
      await api.moverCajita(cajita.id, { monto: m, sentido })
      avisar?.('Listo: moviste la plata. Tu saldo total no cambió.', 'ok')
      avisarCambioRendimientos()
      onCerrar()
    } catch (err) {
      setError(err.message || 'No pudimos mover la plata. Intenta de nuevo.')
      setGuardando(false)
    }
  }

  async function borrar() {
    const ok = await confirmar?.('La plata de la cajita vuelve al saldo principal. Tu saldo total no cambia.', {
      titulo: `¿Quitar la cajita «${cajita.nombre}»?`,
      confirmarTexto: 'Quitar',
      peligro: true,
    })
    if (!ok) return
    try {
      await api.borrarCajita(cajita.id)
      avisarCambioRendimientos()
      onCerrar()
    } catch (err) {
      setError(err.message || 'No pudimos quitar la cajita.')
    }
  }

  return (
    <Hoja onCerrar={onCerrar} ariaLabel={`Mover plata de ${cajita.nombre}`} capa="z-[60]" historial={false}>
      <Encabezado titulo={`Mover plata · ${cajita.nombre}`} onCerrar={onCerrar} />
      <div className="grid grid-cols-2 gap-2 mb-3" role="group" aria-label="Hacia dónde mover">
        {[
          ['entrar', 'Meter a la cajita'],
          ['salir', 'Sacar de la cajita'],
        ].map(([id, texto]) => (
          <button
            key={id}
            type="button"
            aria-pressed={sentido === id}
            onClick={() => setSentido(id)}
            className={`rounded-2xl border py-3 text-sm font-medium min-h-11 ${sentido === id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'}`}
          >
            {texto}
          </button>
        ))}
      </div>
      <CampoMonto etiqueta="¿Cuánto?" value={monto} onValor={setMonto} entero ayuda={`Puedes mover hasta ${PESOS(fmt, tope, moneda)}.`} />
      <p className="text-xs text-ink-soft mt-2">
        Es un movimiento entre tus propios apartados: no es un gasto ni un ingreso y tu saldo total no cambia.
      </p>
      {error && <p role="alert" className="text-sm text-danger mt-3">{error}</p>}
      <div className="mt-4 space-y-2">
        <Boton bloque onClick={mover} cargando={guardando}>
          {guardando ? 'Moviendo...' : 'Mover plata'}
        </Boton>
        <Boton bloque variante="fantasma" onClick={borrar}>
          Quitar esta cajita
        </Boton>
      </div>
    </Hoja>
  )
}

function HojaTasaCuenta({ cuentaId, actual, onCerrar }) {
  const { avisar } = useDialogos() || {}
  const [tasa, setTasa] = useState(actual == null ? '' : String(actual).replace('.', ','))
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function guardar() {
    const t = leerTasa(tasa)
    if (t === null || Number.isNaN(t)) return setError('Escribe la tasa como un número, por ejemplo 0,10.')
    setGuardando(true)
    try {
      await api.editarCuenta(cuentaId, { tasa_ea: t })
      avisar?.('Listo: guardamos la tasa de tu cuenta.', 'ok')
      avisarCambioRendimientos()
      onCerrar()
    } catch (err) {
      setError(err.message || 'No pudimos guardar la tasa. Intenta de nuevo.')
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onCerrar} ariaLabel="Cuánto rinde esta cuenta" capa="z-[60]" historial={false}>
      <Encabezado titulo="¿Cuánto rinde esta cuenta?" onCerrar={onCerrar} />
      <p className="t-apoyo mb-3">
        Escribe la tasa efectiva anual (E.A.) del saldo principal. La encuentras en la app de tu banco. <Ayudita termino="ea" />
      </p>
      <CampoTexto etiqueta="Tasa E.A. (%)" value={tasa} onChange={(e) => setTasa(e.target.value)} inputMode="decimal" placeholder="Ej. 0,10" />
      {error && <p role="alert" className="text-sm text-danger mt-3">{error}</p>}
      <div className="mt-4">
        <Boton bloque onClick={guardar} cargando={guardando}>
          Guardar
        </Boton>
      </div>
    </Hoja>
  )
}

/** Tarjeta «Tu plata trabajando» del Inicio completo: estimado del mes y de 12 meses, lo recibido, y la comparación informativa. */
export default function TarjetaTuPlata() {
  const { fmt } = useBloqueo()
  const { datos } = useRendimientos()
  const [verOpciones, setVerOpciones] = useState(false)
  if (!datos?.hay_cuentas) return null
  const t = datos.total
  const ociosa = datos.comparacion?.ociosa || []
  if (!t.hay_estimacion && !ociosa.length) {
    return (
      <section className="mx-6 mt-4 tarjeta p-4" aria-label="Tu plata trabajando" data-testid="tu-plata">
        <TituloTarjeta />
        <p className="t-cuerpo mt-1">Anota cuánto rinde cada cuenta y te mostramos cuánto gana tu plata.</p>
        <div className="mt-3">
          <Boton to="/cuentas" tam="sm" variante="suave">
            Ver mis cuentas
          </Boton>
        </div>
      </section>
    )
  }
  return (
    <section className="mx-6 mt-4 tarjeta p-4" aria-label="Tu plata trabajando" data-testid="tu-plata">
      <TituloTarjeta />
      {t.hay_estimacion && (
        <>
          <p className="t-cuerpo mt-1" data-testid="tu-plata-mes">
            Tu plata ganó ~{PESOS(fmt, t.mes_corrido)} este mes y ganará ~{PESOS(fmt, t.anio)} en 12 meses.
          </p>
          <p className="t-apoyo mt-1">{AVISO_ESTIMACION}</p>
          {t.recibido_mes != null && (
            <p className="t-apoyo mt-1" data-testid="tu-plata-real">
              Rendimientos que ya te llegaron este mes: {PESOS(fmt, t.recibido_mes)}.
            </p>
          )}
        </>
      )}
      {ociosa.map((o) => (
        <p key={o.cuenta_id} className="t-cuerpo mt-2" data-testid="tu-plata-ociosa">
          Tienes {PESOS(fmt, o.saldo)} en el saldo principal de {o.nombre} ganando {formatTasa(o.tasa_actual)}: con una tasa de referencia de ~{formatTasa(o.tasa_ref)} (la de una cajita o bolsillo) serían ~{PESOS(fmt, o.extra_anual)} más al año.
        </p>
      ))}
      <div className="flex flex-wrap items-center gap-x-4 mt-2">
        <button type="button" onClick={() => setVerOpciones(true)} className="text-sm text-accent font-medium min-h-11 inline-flex items-center">
          Ver tasas de referencia
        </button>
        <Link to="/aprende?l=donde-rinde-mi-plata" className="text-sm text-accent font-medium min-h-11 inline-flex items-center">
          ¿Dónde rinde mi plata?
        </Link>
      </div>
      <p className="t-apoyo">{AVISO_EDUCATIVO}</p>
      {verOpciones && <HojaTasas comparacion={datos.comparacion} onCerrar={() => setVerOpciones(false)} />}
    </section>
  )
}

function TituloTarjeta() {
  return (
    <div className="flex items-center gap-2">
      <span className="w-7 h-7 rounded-lg bg-accent-soft text-accent flex items-center justify-center shrink-0">
        <Icono icono={Sprout} tam="sm" />
      </span>
      <h2 className="t-kicker flex-1">Tu plata trabajando</h2>
    </div>
  )
}

/** Lista neutral (orden alfabético) de tasas de referencia, con fecha y nota. No recomienda ninguna. */
function HojaTasas({ comparacion, onCerrar }) {
  const opciones = comparacion?.opciones || []
  return (
    <Hoja onCerrar={onCerrar} ariaLabel="Tasas de referencia" capa="z-[60]" historial={false}>
      <Encabezado titulo="Tasas de referencia" onCerrar={onCerrar} />
      <p className="t-apoyo mb-3">{AVISO_EDUCATIVO} {comparacion?.nota}</p>
      <ul className="rounded-2xl bg-paper-raised border border-line divide-y divide-line" data-testid="lista-tasas">
        {opciones.map((o) => (
          <li key={o.id} className="px-4 py-3">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-sm font-medium">{o.entidad} · {o.producto}</p>
              <p className="text-sm font-semibold t-cifra shrink-0">{o.tasa_ea == null ? 'Sin dato' : `~${formatTasa(o.tasa_ea)} E.A.`}</p>
            </div>
            <p className="text-xs text-ink-soft">Tasa del {fechaCorta(o.vigente_desde)}. {o.nota}</p>
          </li>
        ))}
      </ul>
      <p className="t-apoyo mt-2">Están en orden alfabético y no son una recomendación: las condiciones cambian.</p>
    </Hoja>
  )
}

/** Renglón del Inicio simple: solo si la persona ya tiene cajitas. */
export function RenglonTuPlata() {
  const { fmt } = useBloqueo()
  const { datos } = useRendimientos()
  if (!datos?.hay_cajitas || !datos.total?.hay_estimacion) return null
  return (
    <Link to="/cuentas" className="mx-6 mt-3 tarjeta p-4 flex items-center gap-3 min-h-[56px]" data-testid="tu-plata-simple">
      <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
        <Icono icono={Sprout} tam="md" />
      </span>
      <span className="t-cuerpo flex-1">Tu plata ganó ~{PESOS(fmt, datos.total.mes_corrido)} este mes <span className="text-ink-soft">(estimado)</span></span>
    </Link>
  )
}
