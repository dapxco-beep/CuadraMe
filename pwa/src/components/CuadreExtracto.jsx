import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Scale, Search, Undo2 } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { leerMonto } from '../lib/cuentaNueva'
import { codigoError, cuerpoEvaluar, mensajeError, ORIENTACION } from '../lib/cuadreExtracto'
import InputMonto from './InputMonto'

// «Cuadre con el banco»: compara el saldo que dice el extracto con lo que suman tus movimientos.
// Nunca cambia nada sin tu permiso: el ajuste y el saldo inicial piden confirmación y se pueden deshacer.
//  - antes de traer (previo): `porImportar` = líneas nuevas marcadas; cuentan como ya traídas. Aquí no se crea el ajuste
//    (primero hay que traer o resolver lo que falta).
//  - después de traer (`despues`): ya se puede crear el ajuste y se recuerda que el mes cuadra.
export default function CuadreExtracto({
  cuentaId, historialId = null, saldos = null, porImportar = [], avisoCuenta = null, despues = false, onCambio, className = '',
}) {
  const [ev, setEv] = useState(null)
  const [manual, setManual] = useState(null)
  const [oculto, setOculto] = useState(false)
  const [panel, setPanel] = useState(null) // 'ajuste' | 'inicial' | 'falta'
  const [falta, setFalta] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [deshacer, setDeshacer] = useState(null)
  const [reforzado, setReforzado] = useState(false)
  const [valorManual, setValorManual] = useState('')
  const [fechaManual, setFechaManual] = useState('')
  const marca = useRef(0)
  const clavePorImportar = porImportar.map((l) => `${l.fecha}|${l.monto}|${l.tipo}`).join(';')

  const cargar = useCallback(async () => {
    const n = ++marca.current
    try {
      const r = await api.cuadreEvaluar(cuerpoEvaluar({ cuentaId, historialId, saldos, manual, porImportar, avisoCuenta, registrar: despues }))
      if (n === marca.current) setEv(r)
    } catch {
      if (n === marca.current) setEv(null) // el cuadre es un extra: si falla no estorba
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cuentaId, historialId, manual, clavePorImportar, avisoCuenta, despues, saldos])

  useEffect(() => {
    cargar()
  }, [cargar])

  if (!ev || oculto) return null
  const moneda = ev.moneda_cuenta || 'COP'
  const f = (v) => formatCOP(Math.abs(v), moneda)

  async function accion(fn, texto) {
    setOcupado(true)
    setError('')
    try {
      const r = await fn()
      setPanel(null)
      setReforzado(false)
      setMensaje(r?.texto || texto)
      setDeshacer(r?.movimiento_id || null)
      await cargar()
      onCambio?.()
    } catch (err) {
      if (codigoError(err) === 'requiere_confirmacion_reforzada') setReforzado(true)
      setError(mensajeError(err))
    } finally {
      setOcupado(false)
    }
  }

  async function verFalta() {
    setPanel(panel === 'falta' ? null : 'falta')
    if (!falta) {
      try {
        setFalta(await api.cuadreQueFalta(cuentaId, historialId))
      } catch (err) {
        setError(mensajeError(err))
      }
    }
  }

  function guardarSaldoManual() {
    const v = leerMonto(valorManual)
    if (Number.isNaN(v) || valorManual === '') return setError('Escribe el saldo que dice tu extracto, solo números.')
    if (!fechaManual && !ev.fecha_corte) return setError('Escribe la fecha de corte del extracto.')
    // En una tarjeta se escribe lo que se DEBE (positivo); el servidor guarda la deuda en negativo.
    const saldo = ev.tipo_cuenta === 'credito' ? -Math.abs(v) : valorManual.trim().startsWith('-') ? -v : v
    const fecha = fechaManual || ev.fecha_corte
    setError('')
    if (historialId) {
      accion(() => api.cuadreSaldos({ historial_id: historialId, saldo_final: saldo, fecha_corte: fecha, confirmar: true }), 'Listo: guardé el saldo de tu extracto.')
    } else {
      setManual({ saldo_final: saldo, fecha_corte: fecha })
    }
  }

  const tono = ev.estado === 'cuadra' ? 'border-cuadra bg-cuadra-soft' : 'border-line bg-paper-raised'
  const acc = ev.acciones || {}
  const ajuste = acc.ajuste
  const bloqueoAjuste = ajuste && (!ajuste.permitido ? ajuste.motivo_bloqueo : !despues ? 'Primero trae las líneas nuevas; después podrás crear el ajuste.' : null)

  return (
    <section className={`rounded-2xl border p-3.5 ${tono} ${className}`} aria-label="Cuadre con el banco" data-testid="cuadre-extracto" data-estado={ev.estado}>
      <h4 className="text-sm font-semibold flex items-center gap-1.5">
        <Scale size={16} aria-hidden="true" /> Cuadre con el banco
      </h4>

      {ev.estado === 'cuadra' && (
        <p className="mt-2 text-xs flex items-start gap-1.5 font-medium" role="status">
          <CheckCircle2 size={16} className="text-cuadra shrink-0" aria-hidden="true" /> {ev.texto}
        </p>
      )}

      {(ev.estado === 'moneda_distinta' || ev.estado === 'antes_de_inicio') && (
        <p className="mt-2 text-xs flex items-start gap-1.5" role="status">
          <AlertTriangle size={16} className="text-accent shrink-0" aria-hidden="true" /> {ev.texto}
        </p>
      )}

      {ev.estado === 'sin_saldo' && (
        <div className="mt-2 text-xs">
          <p>{ev.texto}</p>
          <label className="block mt-2">
            <span className="text-ink-soft">Saldo que dice tu extracto</span>
            <InputMonto negativo value={valorManual} onValor={setValorManual} placeholder="Ej. 1500000" aria-label="Saldo del extracto"
              className="w-full rounded-xl border border-line bg-paper px-3 py-2.5 text-sm mt-1" />
          </label>
          {!ev.fecha_corte && (
            <label className="block mt-2">
              <span className="text-ink-soft">Fecha de corte</span>
              <input type="date" value={fechaManual} onChange={(e) => setFechaManual(e.target.value)} aria-label="Fecha de corte del extracto"
                className="w-full rounded-xl border border-line bg-paper px-3 py-2.5 text-sm mt-1" />
            </label>
          )}
          <button disabled={ocupado} onClick={guardarSaldoManual} className="mt-2 w-full min-h-[44px] rounded-xl bg-accent text-paper-raised text-xs font-semibold disabled:opacity-60">
            Comparar con mis movimientos
          </button>
        </div>
      )}

      {ev.estado === 'diferencia' && (
        <div className="mt-2 text-xs space-y-2">
          <p className="font-semibold flex items-start gap-1.5" data-testid="texto-diferencia">
            <AlertTriangle size={16} className="text-accent shrink-0" aria-hidden="true" /> {ev.texto}
          </p>
          <div>
            <p className="text-ink-soft">Puede ser por:</p>
            <ul className="list-disc pl-5 space-y-0.5">
              {ev.causas.filter((c) => c.probable).concat(ev.causas.filter((c) => !c.probable)).map((c) => (
                <li key={c.codigo} className={c.probable ? 'font-medium' : ''}>{c.texto}</li>
              ))}
            </ul>
          </div>
          {(ev.advertencias || []).map((a) => (
            <p key={a.codigo} className="flex items-start gap-1.5 font-medium" role="status">
              <AlertTriangle size={16} className="text-accent shrink-0" aria-hidden="true" /> {a.texto}
            </p>
          ))}
          <div className="flex flex-col gap-2">
            <button onClick={verFalta} aria-expanded={panel === 'falta'} className="min-h-[44px] rounded-xl border border-line text-xs font-semibold flex items-center justify-center gap-1.5">
              <Search size={16} aria-hidden="true" /> Ver qué puede faltar
            </button>
            {acc.saldo_inicial && (
              <button onClick={() => setPanel(panel === 'inicial' ? null : 'inicial')} aria-expanded={panel === 'inicial'} className="min-h-[44px] rounded-xl border border-line text-xs font-semibold">
                Registrar saldo inicial
              </button>
            )}
            {ajuste && (
              <button onClick={() => setPanel(panel === 'ajuste' ? null : 'ajuste')} disabled={!!bloqueoAjuste} aria-expanded={panel === 'ajuste'}
                className="min-h-[44px] rounded-xl bg-accent text-paper-raised text-xs font-semibold disabled:opacity-50">
                Crear ajuste de saldo
              </button>
            )}
            {bloqueoAjuste && <p className="text-ink-soft" data-testid="motivo-bloqueo">{bloqueoAjuste}</p>}
            <button onClick={() => setOculto(true)} className="min-h-[44px] rounded-xl text-xs font-semibold text-ink-soft">
              Dejarlo así por ahora
            </button>
          </div>

          {panel === 'falta' && (
            <div className="rounded-xl bg-paper border border-line p-3" data-testid="panel-falta">
              {!falta ? <p>Buscando…</p> : (
                <>
                  <p className="font-semibold">En el extracto, sin pareja en tus movimientos</p>
                  <Lista filas={falta.sin_pareja_en_tus_movimientos} vacio="Nada: todas las líneas tienen pareja." f={f} />
                  <p className="font-semibold mt-2">En tus movimientos, que el extracto no respalda</p>
                  <Lista filas={falta.sin_respaldo_en_el_extracto} vacio="Nada: todo lo tuyo aparece en el extracto." f={f} />
                </>
              )}
            </div>
          )}

          {panel === 'inicial' && acc.saldo_inicial && (
            <div className="rounded-xl bg-paper border border-line p-3" data-testid="panel-inicial">
              <p>{acc.saldo_inicial.texto}</p>
              {acc.saldo_inicial.saldo_cuenta_antes !== acc.saldo_inicial.saldo_cuenta_despues && (
                <p className="mt-1 font-medium">
                  El saldo de tu cuenta pasará de {f(acc.saldo_inicial.saldo_cuenta_antes)} a {f(acc.saldo_inicial.saldo_cuenta_despues)}.
                </p>
              )}
              <p className="text-ink-soft mt-1">No cuenta como gasto ni ingreso. Podrás deshacerlo.</p>
              <button disabled={ocupado} onClick={() => accion(() => api.cuadreSaldoInicial({
                cuenta_id: cuentaId, modo: acc.saldo_inicial.modo, historial_id: historialId || undefined,
                saldo_inicial: acc.saldo_inicial.monto, periodo_inicio: acc.saldo_inicial.fecha, confirmar: true,
              }), 'Listo: registré el saldo inicial.')} className="mt-2 w-full min-h-[44px] rounded-xl bg-accent text-paper-raised text-xs font-semibold disabled:opacity-60">
                Sí, registrar saldo inicial
              </button>
            </div>
          )}

          {panel === 'ajuste' && ajuste && !bloqueoAjuste && (
            <div className="rounded-xl bg-paper border border-line p-3" data-testid="panel-ajuste">
              <p>{ajuste.nota}: {ajuste.monto > 0 ? '+' : '-'}{f(ajuste.monto)}.</p>
              <p className="text-ink-soft mt-1">Es un movimiento neutro: no cuenta como gasto ni ingreso. Podrás deshacerlo.</p>
              {(ajuste.grande || reforzado) && (
                <p className="mt-1 font-semibold flex items-start gap-1.5" role="alert">
                  <AlertTriangle size={16} className="text-accent shrink-0" aria-hidden="true" />
                  Es un ajuste grande y puede ocultar un movimiento que falta. Búscalo antes con «Ver qué puede faltar».
                </p>
              )}
              {(ajuste.grande || reforzado) && (
                <label className="flex items-start gap-2 mt-2 min-h-[44px]">
                  <input type="checkbox" checked={reforzado} onChange={(e) => setReforzado(e.target.checked)} className="mt-0.5" />
                  <span>Entiendo y quiero crear el ajuste de todas formas.</span>
                </label>
              )}
              <button disabled={ocupado || ((ajuste.grande) && !reforzado)} onClick={() => accion(() => api.cuadreAjuste({
                cuenta_id: cuentaId, historial_id: historialId || undefined,
                ...(historialId ? {} : { saldo_final: ev.saldo_extracto, fecha_corte: ev.fecha_corte, moneda: manual?.moneda || saldos?.moneda }),
                confirmar: true, confirmar_reforzado: reforzado,
              }), 'Listo: creé el ajuste.')} className="mt-2 w-full min-h-[44px] rounded-xl bg-accent text-paper-raised text-xs font-semibold disabled:opacity-60">
                Sí, crear el ajuste
              </button>
            </div>
          )}
        </div>
      )}

      {mensaje && (
        <p className="mt-2 text-xs flex items-center gap-2" role="status" data-testid="mensaje-cuadre">
          <span className="flex-1">{mensaje}</span>
          {deshacer && (
            <button disabled={ocupado} onClick={() => accion(() => api.cuadreDeshacer(deshacer), 'Listo: lo deshice.').then(() => setDeshacer(null))}
              className="min-h-[44px] px-2 font-semibold text-accent flex items-center gap-1">
              <Undo2 size={16} aria-hidden="true" /> Deshacer
            </button>
          )}
        </p>
      )}
      {error && <p role="alert" className="mt-2 text-xs text-danger">{error}</p>}
      <p className="mt-2 text-[11px] text-ink-soft">{ORIENTACION}</p>
    </section>
  )
}

function Lista({ filas = [], vacio, f }) {
  if (!filas.length) return <p className="text-ink-soft">{vacio}</p>
  return (
    <ul className="divide-y divide-line">
      {filas.slice(0, 20).map((x, i) => (
        <li key={`${x.fecha}-${i}`} className="py-1 flex justify-between gap-2">
          <span className="min-w-0 break-words">{String(x.fecha || '').slice(0, 10)} · {x.descripcion}</span>
          <span className="shrink-0">{x.tipo === 'income' ? '+' : '-'}{f(x.monto)}</span>
        </li>
      ))}
    </ul>
  )
}
