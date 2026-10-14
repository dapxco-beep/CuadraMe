import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, CircleDashed, Scale } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { ORIENTACION, textoEstadoMes } from '../lib/cuadreExtracto'
import CuadreExtracto from './CuadreExtracto'

// Estado del cuadre por mes de UNA cuenta (cuadra / con diferencia / sin extracto). Se puede enganchar en cualquier
// pantalla (p. ej. la cobertura mensual de Traer movimientos): solo necesita `cuentaId`.
//   `datos` (opcional): la respuesta de GET /conciliacion/cuadre?cuenta_id=, si quien lo usa ya la tiene.
export default function CuadreMes({ cuentaId, datos = null, className = '' }) {
  const [d, setD] = useState(datos)
  useEffect(() => {
    if (datos) return setD(datos)
    let vigente = true
    api.cuadreCuenta(cuentaId).then((r) => vigente && setD(r)).catch(() => {})
    return () => {
      vigente = false
    }
  }, [cuentaId, datos])
  if (!d || !d.meses?.length) return null
  return (
    <div className={className} data-testid="cuadre-meses">
      <ul className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {d.meses.map((m) => (
          <li key={m.mes} className="rounded-xl border border-line bg-paper p-2.5 text-xs" data-estado={m.estado} data-dejo={m.dejo_de_cuadrar ? '1' : undefined}>
            <p className="font-semibold truncate">{m.etiqueta}</p>
            <p className="flex items-center gap-1 mt-0.5">
              {m.dejo_de_cuadrar || m.estado === 'diferencia'
                ? <AlertTriangle size={16} className="text-accent shrink-0" aria-hidden="true" />
                : m.estado === 'cuadra'
                  ? <CheckCircle2 size={16} className="text-cuadra shrink-0" aria-hidden="true" />
                  : <CircleDashed size={16} className="text-ink-soft shrink-0" aria-hidden="true" />}
              <span>{textoEstadoMes(m)}</span>
            </p>
            {m.estado === 'diferencia' && <p className="text-ink-soft">Diferencia de {formatCOP(Math.abs(m.diferencia || 0), d.moneda)}</p>}
          </li>
        ))}
      </ul>
      {d.alertas?.map((a) => (
        <p key={a.mes} role="status" className="mt-2 text-xs flex items-start gap-1.5 font-medium">
          <AlertTriangle size={16} className="text-accent shrink-0" aria-hidden="true" /> {a.texto}
        </p>
      ))}
    </div>
  )
}

// Cuenta cuyo saldo no coincide con la suma de sus movimientos (p. ej. creada con un saldo o traída de un respaldo):
// ofrece dejar ese saldo de partida como «Saldo inicial». El saldo de la cuenta no cambia y se puede deshacer.
function SaldoInicialSinExplicar({ cuentaId, diag, moneda, onHecho }) {
  const [ocupado, setOcupado] = useState(false)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [id, setId] = useState(null)
  async function hacer(fn) {
    setOcupado(true)
    setError('')
    try {
      const r = await fn()
      setMsg(r.texto || 'Listo.')
      setId(r.movimiento_id || null)
      onHecho()
    } catch (err) {
      setError(err.message || 'No pudimos hacerlo. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setOcupado(false)
    }
  }
  return (
    <div className="rounded-xl bg-paper border border-line p-3 mt-2 text-xs" data-testid="saldo-inicial-sin-explicar">
      <p>Hay {formatCOP(Math.abs(diag.diferencia), moneda)} en el saldo de esta cuenta que no vienen de ningún movimiento. Puedes registrarlos como «Saldo inicial»: tu saldo no cambia y no cuenta como gasto ni ingreso.</p>
      <button disabled={ocupado} onClick={() => hacer(() => api.cuadreSaldoInicial({ cuenta_id: cuentaId, modo: 'sin_explicar', confirmar: true }))}
        className="mt-2 w-full min-h-[44px] rounded-xl bg-accent text-paper-raised font-semibold disabled:opacity-60">
        Registrar saldo inicial
      </button>
      {msg && <p role="status" className="mt-2">{msg}</p>}
      {id && <button disabled={ocupado} onClick={() => hacer(() => api.cuadreDeshacer(id)).then(() => setId(null))} className="min-h-[44px] font-semibold text-accent">Deshacer</button>}
      {error && <p role="alert" className="mt-2 text-danger">{error}</p>}
    </div>
  )
}

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const fechaCorta = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? `${+m[3]} ${MESES[+m[2] - 1]} ${m[1]}` : ''
}

// Tarjeta «Cuadre con el banco» del detalle de una cuenta: última fecha que cuadró, diferencia actual y «Revisar».
export function TarjetaCuadreBanco({ cuentaId, moneda = 'COP', onCambio }) {
  const [d, setD] = useState(null)
  const [revisando, setRevisando] = useState(false)
  useEffect(() => {
    let vigente = true
    api.cuadreCuenta(cuentaId).then((r) => vigente && setD(r)).catch(() => {})
    return () => {
      vigente = false
    }
  }, [cuentaId])
  if (!d) return null
  const actual = d.estado_actual
  const ultimo = d.ultimo_cuadre
  const diag = d.diagnostico
  const sinExtractos = !d.meses?.length
  return (
    <section className="rounded-2xl bg-paper-raised border border-line p-4 mt-3" aria-label="Cuadre con el banco" data-testid="tarjeta-cuadre-banco">
      <h3 className="text-sm font-semibold flex items-center gap-1.5"><Scale size={16} aria-hidden="true" /> Cuadre con el banco</h3>
      {sinExtractos ? (
        <p className="text-xs text-ink-soft mt-1">Aún no has comparado esta cuenta con un extracto. Sube uno y vemos si tu saldo cuadra con el del banco.</p>
      ) : (
        <>
          <p className="text-xs mt-1" data-testid="ultimo-cuadre">
            {ultimo ? `Última vez que cuadró: ${fechaCorta(ultimo.fecha_corte) || ultimo.mes}.` : 'Todavía no hay un mes que cuadre.'}
          </p>
          {actual && (
            <p className="text-xs mt-0.5" data-testid="diferencia-actual">
              {actual.estado === 'cuadra' ? 'Hoy no hay diferencia con tu último extracto.'
                : `Diferencia con tu último extracto: ${formatCOP(Math.abs(actual.diferencia || 0), moneda)}.`}
            </p>
          )}
        </>
      )}
      {diag?.descuadre && <p className="text-xs mt-1 font-medium" data-testid="diagnostico-saldo">{diag.texto}</p>}
      {d.alertas?.length > 0 && (
        <p role="status" className="text-xs mt-1 font-medium flex items-start gap-1.5">
          <AlertTriangle size={16} className="text-accent shrink-0" aria-hidden="true" /> {d.alertas[0].texto}
        </p>
      )}
      {!sinExtractos && <CuadreMes cuentaId={cuentaId} datos={d} className="mt-2" />}
      <button onClick={() => setRevisando((v) => !v)} aria-expanded={revisando}
        className="mt-3 w-full min-h-[44px] rounded-xl border border-line text-xs font-semibold">
        Revisar
      </button>
      {revisando && (
        <div className="mt-2" data-testid="revisar-cuadre">
          {actual?.historial_id ? (
            <CuadreExtracto cuentaId={cuentaId} historialId={actual.historial_id} despues onCambio={() => { onCambio?.(); api.cuadreCuenta(cuentaId).then(setD).catch(() => {}) }} />
          ) : (
            <p className="text-xs text-ink-soft">Para revisar el cuadre, sube el extracto de tu banco desde «Comparar con mi banco».</p>
          )}
          {diag?.descuadre && <SaldoInicialSinExplicar cuentaId={cuentaId} diag={diag} moneda={moneda} onHecho={() => { onCambio?.(); api.cuadreCuenta(cuentaId).then(setD).catch(() => {}) }} />}
        </div>
      )}
      <p className="mt-2 text-[11px] text-ink-soft">{ORIENTACION}</p>
    </section>
  )
}
