import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CalendarClock, CheckCircle2, Flag, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { mensajeAmable } from '../lib/mensajes'
import {
  AYUDA_ELEGIR, MODOS, OPCIONES_MESES, avisosFaltantes, descripcionPunto, fechaDesdeMeses, fechaLarga, hoyISO,
  parsearMonto,
} from '../lib/puntoPartida'

/**
 * Punto de partida: «empezar desde hoy» o «recrear mi histórico». Un solo componente para:
 *   variante="primera"  la primera vez (arriba de Traer movimientos, o donde se conecte el primer uso)
 *   variante="perfil"   Perfil → «Punto de partida»: ver lo elegido y cambiarlo
 *
 * Props:
 *   inicial     (opcional) el resumen de GET /perfil/punto-de-partida; sin él, el componente lo pide.
 *   onGuardado  se llama con la respuesta al guardar.
 *   onPosponer  (solo «primera») muestra «Decidir después».
 *   onSubir     (opcional) qué hacer con «Subir mis extractos»; sin él es un enlace a /sincronizacion.
 *
 * Reglas (las aplica el servidor): hacia atrás permite importar más; hacia adelante oculta lo anterior
 * de informes y consejos; nunca se borra nada.
 */
export default function PuntoDePartida({ variante = 'perfil', inicial = null, onGuardado, onPosponer, onSubir }) {
  const { cuentas = [], recargar: recargarCuentas } = useCuentas() || {}
  const [pp, setPp] = useState(inicial)
  const [cargando, setCargando] = useState(!inicial)
  const [editando, setEditando] = useState(variante === 'primera')
  const [modo, setModo] = useState(null)
  const [meses, setMeses] = useState(6)
  const [otraFecha, setOtraFecha] = useState(false)
  const [fecha, setFecha] = useState('')
  const [saldos, setSaldos] = useState({}) // cuenta_id -> { inicial, actual } (texto)
  const [confirmo, setConfirmo] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [cobertura, setCobertura] = useState(null)
  const [conciliacion, setConciliacion] = useState(null)
  const [aviso, setAviso] = useState('')
  const montado = useRef(true)

  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
    }
  }, [])

  const cargarDetalle = useCallback(async () => {
    try {
      const [cob, con] = await Promise.all([
        api.coberturaPuntoDePartida?.().catch(() => null),
        api.conciliacionPuntoDePartida?.().catch(() => null),
      ])
      if (!montado.current) return
      setCobertura(cob || null)
      setConciliacion(con || null)
    } catch {
      /* el detalle es un extra: sin él se ve lo básico */
    }
  }, [])

  useEffect(() => {
    if (inicial) return undefined
    let vigente = true
    Promise.resolve(api.puntoDePartida?.())
      .then((r) => {
        if (!vigente) return
        setPp(r || { definido: false })
        setCargando(false)
      })
      .catch(() => vigente && (setPp({ definido: false }), setCargando(false)))
    return () => {
      vigente = false
    }
  }, [inicial])

  useEffect(() => {
    if (pp?.definido && pp.modo === 'historico' && !editando) cargarDetalle()
  }, [pp?.definido, pp?.modo, pp?.fecha, editando, cargarDetalle])

  // Al elegir una tarjeta: los saldos arrancan con lo que la app ya tiene (la persona corrige).
  function elegir(id) {
    setModo(id)
    setError('')
    setConfirmo(false)
    setSaldos((prev) => {
      const sig = { ...prev }
      for (const c of cuentas) {
        if (!sig[c.id]) {
          const guardado = pp?.saldos?.[c.id] || {}
          const base = guardado.actual ?? c.saldo ?? 0
          sig[c.id] = { inicial: guardado.inicial != null ? String(guardado.inicial) : '', actual: String(base) }
        }
      }
      return sig
    })
  }

  const fechaNueva = modo === 'hoy' ? hoyISO() : otraFecha ? fecha : fechaDesdeMeses(meses)
  const adelanta = Boolean(pp?.definido && pp.fecha && fechaNueva && fechaNueva > pp.fecha)

  async function guardar() {
    if (!modo || guardando) return
    if (modo === 'historico' && otraFecha && !fecha) {
      setError('Elige la fecha desde la que quieres recrear tu histórico.')
      return
    }
    if (adelanta && !confirmo) {
      setError('Marca la casilla para confirmar: lo anterior se oculta de tus informes (no se borra nada).')
      return
    }
    setGuardando(true)
    setError('')
    const cuerpo = { modo, saldos: {}, ajustar_saldos: modo === 'hoy' }
    if (modo === 'historico') {
      if (otraFecha) cuerpo.fecha = fecha
      else cuerpo.meses = meses
    }
    for (const c of cuentas) {
      const s = saldos[c.id] || {}
      const actual = parsearMonto(s.actual)
      const inicial = parsearMonto(s.inicial)
      if (actual != null || inicial != null) cuerpo.saldos[c.id] = { actual, inicial: modo === 'hoy' ? actual : inicial }
    }
    // En «hoy» el saldo que la persona escribe es el punto de partida: solo se ajusta si cambió.
    if (modo === 'hoy') {
      cuerpo.ajustar_saldos = cuentas.some((c) => cuerpo.saldos[c.id] && cuerpo.saldos[c.id].actual !== (c.saldo ?? 0))
    }
    try {
      const r = await api.guardarPuntoDePartida(cuerpo)
      if (!montado.current) return
      setPp(r)
      setEditando(false)
      setConfirmo(false)
      setAviso(
        modo === 'hoy'
          ? `Listo: tu punto de partida es hoy, ${fechaLarga(r.fecha)}.`
          : `Listo: recreamos tu histórico desde el ${fechaLarga(r.fecha)}.`
      )
      recargarCuentas?.()
      onGuardado?.(r)
    } catch (err) {
      if (montado.current) setError(mensajeAmable(err?.message, { porDefecto: 'No pude guardar tu punto de partida. Intenta de nuevo.' }))
    } finally {
      if (montado.current) setGuardando(false)
    }
  }

  async function ajustar() {
    setGuardando(true)
    setError('')
    try {
      const r = await api.ajustarSaldosPuntoDePartida()
      setAviso(r?.ajustados ? `Listo: ajusté el saldo de ${r.ajustados} ${r.ajustados === 1 ? 'cuenta' : 'cuentas'}. El ajuste no cuenta como gasto ni ingreso.` : 'No había nada que ajustar.')
      recargarCuentas?.()
      await cargarDetalle()
    } catch (err) {
      setError(mensajeAmable(err?.message, { porDefecto: 'No pude ajustar el saldo. Intenta de nuevo.' }))
    } finally {
      if (montado.current) setGuardando(false)
    }
  }

  if (cargando) return <p className="text-sm text-ink-soft" role="status">Cargando…</p>

  // ── Resumen de lo elegido (Perfil, o recién guardado) ─────────────────
  if (pp?.definido && !editando) {
    const avisos = avisosFaltantes(cobertura)
    const filas = (conciliacion?.cuentas || []).filter((f) => f.coincide !== null)
    const desajustes = filas.filter((f) => f.coincide === false)
    return (
      <div className="rounded-2xl bg-paper-raised border border-line p-4" data-testid="punto-partida-resumen">
        <p className="flex items-center gap-2 text-sm font-semibold">
          <Flag size={20} className="text-accent shrink-0" aria-hidden="true" />
          {descripcionPunto(pp)}
        </p>
        <p className="text-xs text-ink-soft mt-1">
          {pp.modo === 'hoy'
            ? 'Informes y consejos cuentan desde esa fecha. Los correos y extractos anteriores no se muestran.'
            : 'Informes y consejos cuentan desde esa fecha. Pídele a tu banco los extractos que falten y súbelos.'}
        </p>
        {aviso && <p className="text-xs font-medium text-cuadra mt-2" role="status">{aviso}</p>}
        {(pp.anteriores?.correos > 0 || pp.anteriores?.extractos > 0) && (
          <p className="text-xs text-ink-soft mt-2" data-testid="anteriores-ignorados">
            {pp.anteriores.correos > 0 && `${pp.anteriores.correos} ${pp.anteriores.correos === 1 ? 'correo anterior' : 'correos anteriores'}`}
            {pp.anteriores.correos > 0 && pp.anteriores.extractos > 0 ? ' y ' : ''}
            {pp.anteriores.extractos > 0 && `${pp.anteriores.extractos} ${pp.anteriores.extractos === 1 ? 'extracto anterior' : 'extractos anteriores'}`}
            {' a tu fecha de inicio no se muestran.'}
          </p>
        )}

        {pp.modo === 'historico' && (
          <div className="mt-3 space-y-3">
            {avisos.length > 0 ? (
              <div className="rounded-xl bg-accent-soft px-3 py-2.5" data-testid="faltan-extractos">
                {avisos.map((a) => (
                  <p key={a.cuentaId} className="text-xs">
                    <span className="font-semibold">{a.nombre}.</span> {a.texto}.
                  </p>
                ))}
                <div className="mt-2">
                  {onSubir ? (
                    <button onClick={onSubir} className="min-h-[44px] text-xs font-semibold text-accent underline">Subir mis extractos</button>
                  ) : (
                    <Link to="/sincronizacion" state={{ abrir: 'subir' }} className="inline-flex items-center min-h-[44px] text-xs font-semibold text-accent underline">
                      Subir mis extractos
                    </Link>
                  )}
                </div>
              </div>
            ) : (
              cobertura?.cuentas?.length > 0 && (
                <p className="flex items-center gap-1.5 text-xs font-medium text-cuadra">
                  <CheckCircle2 size={16} aria-hidden="true" /> Tienes los extractos de todos los meses.
                </p>
              )
            )}

            {filas.length > 0 && (
              <div data-testid="saldo-reconstruido">
                <p className="text-xs font-semibold mb-1">Saldo reconstruido frente a tu saldo actual</p>
                <ul className="space-y-1">
                  {filas.map((f) => (
                    <li key={f.cuenta_id} className="flex items-start justify-between gap-2 text-xs">
                      <span className="min-w-0 truncate">{f.nombre}</span>
                      <span className={`shrink-0 ${f.coincide ? 'text-cuadra' : 'text-danger'}`}>
                        {f.coincide ? '✓ Coincide' : `✕ Difiere en ${formatMoneda(Math.abs(f.diferencia))}`}
                      </span>
                    </li>
                  ))}
                </ul>
                {desajustes.length > 0 ? (
                  <div className="mt-2">
                    <p className="text-xs text-ink-soft">
                      Si crees que tu saldo real es el que declaraste, puedo hacer un «ajuste de saldo». No cuenta como gasto ni como ingreso.
                    </p>
                    <button
                      onClick={ajustar}
                      disabled={guardando}
                      className="mt-1 min-h-[44px] rounded-xl border border-line px-4 text-sm font-semibold disabled:opacity-60"
                    >
                      {guardando ? 'Ajustando…' : 'Ajustar el saldo'}
                    </button>
                  </div>
                ) : (
                  <p className="flex items-center gap-1.5 text-xs font-medium text-cuadra mt-2">
                    <CheckCircle2 size={16} aria-hidden="true" /> Tu saldo reconstruido coincide con el actual.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
        {error && <p className="text-xs text-danger mt-2" role="alert">{error}</p>}

        {variante === 'perfil' && (
          <button
            onClick={() => { setEditando(true); setAviso(''); setModo(null) }}
            className="mt-3 min-h-[44px] rounded-xl border border-line px-4 text-sm font-semibold"
          >
            Cambiar mi punto de partida
          </button>
        )}
      </div>
    )
  }

  // ── Elegir ─────────────────────────────────────────────────────────────
  return (
    <div className="rounded-2xl bg-paper-raised border border-line p-4" data-testid="punto-partida-elegir">
      <p className="flex items-center gap-2 text-sm font-semibold">
        <Flag size={20} className="text-accent shrink-0" aria-hidden="true" />
        ¿Desde cuándo quieres llevar tus cuentas?
      </p>
      <p className="text-xs text-ink-soft mt-1">{AYUDA_ELEGIR}</p>

      <div role="radiogroup" aria-label="Punto de partida" className="grid gap-2.5 mt-3">
        {Object.values(MODOS).map((m) => {
          const activo = modo === m.id
          const Icono = m.id === 'hoy' ? Sparkles : CalendarClock
          return (
            <button
              key={m.id}
              type="button"
              role="radio"
              aria-checked={activo}
              onClick={() => elegir(m.id)}
              data-testid={`modo-${m.id}`}
              className={`text-left rounded-2xl border p-3.5 min-h-[44px] ${activo ? 'border-accent bg-accent-soft' : 'border-line bg-paper'}`}
            >
              <span className="flex items-center gap-2 text-sm font-semibold">
                <Icono size={20} className="text-accent shrink-0" aria-hidden="true" />
                <span className="min-w-0">{m.titulo}</span>
                {m.recomendado && (
                  <span className="ml-auto shrink-0 text-[11px] font-bold rounded-full bg-cuadra-soft text-cuadra px-2 py-0.5">Recomendado</span>
                )}
              </span>
              <span className="block text-xs mt-1.5">{m.explicacion}</span>
              <span className="block text-xs text-ink-soft mt-1">{m.ejemplo}</span>
            </button>
          )
        })}
      </div>

      {modo === 'historico' && (
        <fieldset className="mt-4">
          <legend className="text-xs font-semibold mb-2">¿Desde cuándo?</legend>
          <div className="flex flex-wrap gap-2">
            {OPCIONES_MESES.map((n) => (
              <button
                key={n}
                type="button"
                aria-pressed={!otraFecha && meses === n}
                onClick={() => { setOtraFecha(false); setMeses(n) }}
                className={`min-h-[44px] px-4 rounded-xl border text-sm font-semibold ${!otraFecha && meses === n ? 'border-accent bg-accent-soft' : 'border-line'}`}
              >
                {n} meses
              </button>
            ))}
            <button
              type="button"
              aria-pressed={otraFecha}
              onClick={() => setOtraFecha(true)}
              className={`min-h-[44px] px-4 rounded-xl border text-sm font-semibold ${otraFecha ? 'border-accent bg-accent-soft' : 'border-line'}`}
            >
              Otra fecha
            </button>
          </div>
          {otraFecha && (
            <label className="block mt-2">
              <span className="text-xs text-ink-soft">Fecha de inicio</span>
              <input
                type="date"
                value={fecha}
                max={hoyISO()}
                onChange={(e) => setFecha(e.target.value)}
                aria-label="Fecha de inicio"
                className="w-full mt-1 rounded-xl border border-line bg-paper px-3 py-2.5"
              />
            </label>
          )}
          <p className="text-xs text-ink-soft mt-2">
            Empezaremos el {fechaLarga(fechaNueva) || '…'}. Te mostraré qué extractos tienes y cuáles faltan.
          </p>
        </fieldset>
      )}

      {modo && cuentas.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold mb-2">
            {modo === 'hoy' ? 'Saldo de hoy de cada cuenta' : 'Saldos (opcional: si no los sabes, déjalos vacíos)'}
          </p>
          <div className="space-y-2.5">
            {cuentas.map((c) => (
              <div key={c.id} className="rounded-xl bg-paper border border-line p-3">
                <p className="text-sm font-medium truncate">{c.icono} {c.nombre}</p>
                {modo === 'historico' && (
                  <label className="block mt-2">
                    <span className="text-[11px] text-ink-soft">Saldo al inicio ({fechaLarga(fechaNueva) || 'esa fecha'})</span>
                    <input
                      inputMode="decimal"
                      value={saldos[c.id]?.inicial ?? ''}
                      onChange={(e) => setSaldos((s) => ({ ...s, [c.id]: { ...s[c.id], inicial: e.target.value } }))}
                      aria-label={`Saldo al inicio de ${c.nombre}`}
                      placeholder="Si lo sabes"
                      className="w-full mt-0.5 rounded-xl border border-line bg-paper-raised px-3 py-2"
                    />
                  </label>
                )}
                <label className="block mt-2">
                  <span className="text-[11px] text-ink-soft">
                    {modo === 'hoy' ? 'Saldo de hoy (según tu banco)' : 'Saldo actual (según tu banco)'}
                  </span>
                  <input
                    inputMode="decimal"
                    value={saldos[c.id]?.actual ?? ''}
                    onChange={(e) => setSaldos((s) => ({ ...s, [c.id]: { ...s[c.id], actual: e.target.value } }))}
                    aria-label={`Saldo de ${c.nombre}`}
                    className="w-full mt-0.5 rounded-xl border border-line bg-paper-raised px-3 py-2"
                  />
                </label>
              </div>
            ))}
          </div>
          {modo === 'hoy' && (
            <p className="text-xs text-ink-soft mt-2">
              Si cambias un saldo, la cuenta se ajusta con un «ajuste de saldo» que no cuenta como gasto ni ingreso.
            </p>
          )}
        </div>
      )}

      {adelanta && (
        <label className="flex items-start gap-2 mt-3 text-xs min-h-[44px]">
          <input
            type="checkbox"
            checked={confirmo}
            onChange={(e) => setConfirmo(e.target.checked)}
            className="w-4 h-4 mt-0.5 accent-accent shrink-0"
          />
          <span>
            Entiendo que lo anterior al {fechaLarga(fechaNueva)} se oculta de informes y consejos. No se borra nada y
            puedo volver atrás cuando quiera.
          </span>
        </label>
      )}

      {error && (
        <p className="flex items-start gap-1.5 text-xs text-danger mt-3" role="alert">
          <AlertTriangle size={16} className="shrink-0" aria-hidden="true" /> {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2 mt-4">
        <button
          type="button"
          onClick={guardar}
          disabled={!modo || guardando}
          className="flex-1 min-h-[44px] rounded-xl bg-ink text-paper text-sm font-semibold disabled:opacity-50"
        >
          {guardando ? 'Guardando…' : modo === 'historico' ? 'Recrear mi histórico' : modo === 'hoy' ? 'Empezar desde hoy' : 'Elige una opción'}
        </button>
        {variante === 'primera' && onPosponer && (
          <button type="button" onClick={onPosponer} className="min-h-[44px] px-3 text-sm font-semibold text-ink-soft">
            Decidir después
          </button>
        )}
        {variante === 'perfil' && pp?.definido && (
          <button type="button" onClick={() => { setEditando(false); setError('') }} className="min-h-[44px] px-3 text-sm font-semibold text-ink-soft">
            Cancelar
          </button>
        )}
      </div>
    </div>
  )
}
