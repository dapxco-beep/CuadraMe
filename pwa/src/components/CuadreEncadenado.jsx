import { useCallback, useEffect, useState } from 'react'
import { Link, useInRouterContext } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, CircleDashed, Link2Off, Scale, TrendingUp, Undo2 } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { ORIENTACION, mensajeError } from '../lib/cuadreExtracto'
import { ESTADO_MES, aFilas, firmado } from '../lib/cuadreEncadenado'

const ICONO = { cuadra: CheckCircle2, diferencia: AlertTriangle, falta_extracto: CircleDashed, cadena_rota: Link2Off, arrastra: TrendingUp, solo_saldo_inicial: AlertTriangle }

export function EnlaceInterno({ to, children, className }) {
  const enRouter = useInRouterContext()
  return enRouter ? <Link to={to} className={className}>{children}</Link> : <a href={to} className={className}>{children}</a>
}

// Pide el saldo que dice el extracto cuando el PDF no lo trae (p. ej. Nu). Se guarda con origen «manual».
function SaldoAMano({ item, moneda, onGuardado }) {
  const [saldo, setSaldo] = useState('')
  const [fecha, setFecha] = useState(item.fecha_sugerida || '')
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState('')
  async function guardar(e) {
    e.preventDefault()
    const n = Number(String(saldo).replace(/\./g, '').replace(',', '.'))
    if (!Number.isFinite(n) || !fecha) return setError('Escribe el saldo y la fecha de corte que dice tu extracto.')
    setOcupado(true)
    setError('')
    try {
      await api.cuadreSaldos({ historial_id: item.historial_id, saldo_final: n, fecha_corte: fecha, confirmar: true })
      onGuardado()
    } catch (err) {
      setError(mensajeError(err))
    } finally {
      setOcupado(false)
    }
  }
  return (
    <form onSubmit={guardar} className="rounded-xl bg-paper-raised p-3 text-xs" data-testid="saldo-a-mano">
      <p>{item.texto}</p>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-end">
        <label className="flex-1 flex flex-col gap-1 text-ink-soft">
          Saldo del extracto ({moneda})
          <input inputMode="decimal" value={saldo} onChange={(e) => setSaldo(e.target.value)} placeholder="Ej. 1.250.000"
            className="min-h-11 rounded-xl border border-line bg-paper-raised px-3 text-sm text-ink" />
        </label>
        <label className="flex-1 flex flex-col gap-1 text-ink-soft">
          Fecha de corte
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)}
            className="min-h-11 rounded-xl border border-line bg-paper-raised px-3 text-sm text-ink" />
        </label>
        <button type="submit" disabled={ocupado} className="min-h-11 rounded-xl bg-accent text-paper-raised font-semibold px-4 disabled:opacity-60">
          {ocupado ? 'Guardando...' : 'Guardar saldo'}
        </button>
      </div>
      {error && <p role="alert" className="mt-2 text-danger">{error}</p>}
    </form>
  )
}

// Una acción de reparación: SIEMPRE pide confirmación explícita antes de tocar nada.
export function Accion({ accion, onHecho, moneda, ocupado, setOcupado }) {
  const [pidiendo, setPidiendo] = useState(false)
  const [entiendo, setEntiendo] = useState(false)
  const [error, setError] = useState('')
  const [hecho, setHecho] = useState(null)
  const fuerte = accion.tipo === 'ajuste'
  const sinConfirmar = accion.tipo === 'revisar_duplicado' || accion.tipo === 'revisar_extracto'

  async function ejecutar() {
    setOcupado(true)
    setError('')
    try {
      let r = {}
      if (accion.tipo === 'importar_lineas') r = await api.importarFaltantes(accion.historial_id, accion.fingerprints, {}, null)
      else if (accion.tipo === 'saldo_inicial') {
        r = await api.cuadreSaldoInicial({ cuenta_id: accion.cuenta_id, modo: 'extracto', historial_id: accion.historial_id,
          saldo_inicial: accion.saldo_inicial, periodo_inicio: accion.periodo_inicio, confirmar: true })
      } else if (accion.tipo === 'ajuste') {
        r = await api.cuadreAjuste({ cuenta_id: accion.cuenta_id, historial_id: accion.historial_id, confirmar: true, confirmar_reforzado: true })
      }
      setPidiendo(false)
      setHecho({ id: r.movimiento_id || null, texto: r.texto || 'Listo.' })
      onHecho()
    } catch (err) {
      setError(mensajeError(err))
    } finally {
      setOcupado(false)
    }
  }
  async function deshacer() {
    setOcupado(true)
    try {
      await api.cuadreDeshacer(hecho.id)
      setHecho(null)
      onHecho()
    } catch (err) {
      setError(mensajeError(err))
    } finally {
      setOcupado(false)
    }
  }

  if (hecho) {
    return (
      <div className="text-xs" role="status">
        <p className="font-medium">{hecho.texto}</p>
        {hecho.id && (
          <button type="button" disabled={ocupado} onClick={deshacer} className="mt-1 min-h-11 inline-flex items-center gap-1.5 font-semibold text-accent">
            <Undo2 size={16} aria-hidden="true" /> Deshacer
          </button>
        )}
      </div>
    )
  }
  if (accion.tipo === 'revisar_duplicado') {
    return <EnlaceInterno to={accion.ruta || '/buscar-duplicados'} className="min-h-11 inline-flex items-center text-xs font-semibold text-accent">{accion.texto}</EnlaceInterno>
  }
  if (accion.tipo === 'revisar_extracto') {
    return <EnlaceInterno to="/sincronizacion#extractos" className="min-h-11 inline-flex items-center text-xs font-semibold text-accent">{accion.texto}</EnlaceInterno>
  }
  return (
    <div className="text-xs">
      {!pidiendo ? (
        <button type="button" disabled={ocupado} onClick={() => setPidiendo(true)}
          className={`min-h-11 w-full rounded-xl font-semibold px-3 disabled:opacity-60 ${fuerte ? 'border border-line text-ink-soft' : 'bg-accent text-paper-raised'}`}>
          {accion.texto}
        </button>
      ) : (
        <div className="rounded-xl bg-paper-raised p-3" role="group" aria-label={`Confirmar: ${accion.texto}`}>
          <p className="font-semibold">{accion.texto}</p>
          {accion.confirmacion && <p className={`mt-1 ${fuerte ? 'text-danger font-medium' : 'text-ink-soft'}`}>{accion.confirmacion}</p>}
          {fuerte && (
            <label className="mt-2 flex items-start gap-2 min-h-11">
              <input type="checkbox" checked={entiendo} onChange={(e) => setEntiendo(e.target.checked)} className="mt-0.5" />
              <span>Entiendo que puede ocultar un movimiento que falta ({formatCOP(Math.abs(accion.monto || 0), moneda)}).</span>
            </label>
          )}
          <div className="mt-2 flex gap-2">
            <button type="button" disabled={ocupado || (fuerte && !entiendo)} onClick={ejecutar}
              className="min-h-11 flex-1 rounded-xl bg-accent text-paper-raised font-semibold disabled:opacity-50">
              {ocupado ? 'Un momento...' : 'Sí, hacerlo'}
            </button>
            <button type="button" disabled={ocupado} onClick={() => setPidiendo(false)} className="min-h-11 flex-1 rounded-xl border border-line font-semibold">
              Cancelar
            </button>
          </div>
        </div>
      )}
      {error && <p role="alert" className="mt-2 text-danger">{error}</p>}
    </div>
  )
}

/**
 * «Cuadre mes a mes» de UNA cuenta: tabla mes | el banco dice | tu app dice | diferencia | estado, el mes culpable
 * resaltado, la frase en lenguaje llano y la acción sugerida (con confirmación). Se calcula en el servidor al
 * consultar (GET /conciliacion/cuadre/encadenado). `datos` opcional: la misma respuesta si quien lo usa ya la tiene.
 */
export default function CuadreEncadenado({ cuentaId, moneda = 'COP', datos = null, onCambio, className = '', id }) {
  const [d, setD] = useState(datos)
  const [ocupado, setOcupado] = useState(false)
  useEffect(() => { if (datos) setD(datos) }, [datos])
  const cargar = useCallback(() => (
    Promise.resolve().then(() => api.cuadreEncadenado(cuentaId)).then((r) => r && setD(r)).catch(() => {})
  ), [cuentaId])
  useEffect(() => {
    if (datos) return undefined
    let vigente = true
    Promise.resolve().then(() => api.cuadreEncadenado(cuentaId)).then((r) => vigente && r && setD(r)).catch(() => {})
    return () => { vigente = false }
  }, [cuentaId, datos])

  // Saldos que la app puede leer sola (se vuelve a traer el extracto del correo): se piden sin botón, una vez.
  const releyendo = !!d?.sin_saldo?.some((s) => s.releyendo)
  const [lecturaHecha, setLecturaHecha] = useState(false)
  useEffect(() => {
    if (!releyendo || lecturaHecha) return undefined
    let vigente = true
    Promise.resolve().then(() => api.cuadreReleerSaldos())
      .catch(() => {})
      .then(() => { if (vigente) { setLecturaHecha(true); cargar() } })
    return () => { vigente = false }
  }, [releyendo, lecturaHecha, cargar])

  if (!d || (!d.meses?.length && !d.sin_saldo?.length)) return null
  const cur = d.moneda || moneda
  const filas = aFilas(d.meses || [])
  const problemas = (d.meses || []).filter((m) => ['diferencia', 'solo_saldo_inicial', 'cadena_rota'].includes(m.estado))
  const hecho = () => { cargar(); onCambio?.() }

  return (
    <section id={id} className={`rounded-2xl bg-paper p-4 ${className}`} aria-label="Cuadre mes a mes" data-testid="cuadre-encadenado">
      <h3 className="text-sm font-semibold flex items-center gap-1.5">
        <Scale size={16} aria-hidden="true" /> Cuadre mes a mes{d.cuenta ? ` · ${d.cuenta}` : ''}
      </h3>
      {d.resumen && <p className="text-sm mt-1.5 font-medium" data-testid="cuadre-resumen">{d.resumen}</p>}
      {d.cuadra && <p className="text-xs mt-1.5 flex items-center gap-1.5"><CheckCircle2 size={16} className="text-cuadra shrink-0" aria-hidden="true" /> Todos los meses con extracto cuadran con tu banco.</p>}

      {d.sin_saldo?.length > 0 && (
        <div className="mt-2 flex flex-col gap-2">
          {d.sin_saldo.map((s) => (s.releyendo && !lecturaHecha
            ? <p key={s.historial_id} className="rounded-xl bg-paper-raised p-3 text-xs text-ink-soft" role="status" data-testid="leyendo-saldos">Leyendo los saldos de tus extractos…</p>
            : <SaldoAMano key={s.historial_id} item={s.releyendo ? { ...s, texto: 'No pude leer el saldo de este extracto. Escríbelo una vez y listo.' } : s} moneda={cur} onGuardado={hecho} />))}
        </div>
      )}

      {filas.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs">
            <caption className="sr-only">Cada mes contra lo que dice el banco</caption>
            <thead>
              <tr className="text-left text-ink-soft">
                <th scope="col" className="py-1.5 pr-2 font-semibold">Mes</th>
                <th scope="col" className="py-1.5 pr-2 font-semibold text-right">El banco dice</th>
                <th scope="col" className="py-1.5 pr-2 font-semibold text-right">Tu app dice</th>
                <th scope="col" className="py-1.5 pr-2 font-semibold text-right">Diferencia</th>
                <th scope="col" className="py-1.5 font-semibold">Estado</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => {
                const e = ESTADO_MES[f.estado] || ESTADO_MES.cuadra
                const Ico = ICONO[f.estado] || CheckCircle2
                const malo = f.culpable
                return (
                  <tr key={f.mes} data-estado={f.estado} data-culpable={malo ? '1' : undefined}
                    className={`border-t border-line ${malo ? 'bg-accent/10' : ''}`}>
                    <th scope="row" className="py-2 pr-2 text-left font-semibold">{f.etiqueta}</th>
                    <td className="py-2 pr-2 text-right tabular-nums">{f.banco_cambio == null ? '—' : firmado(f.banco_cambio, cur)}</td>
                    <td className="py-2 pr-2 text-right tabular-nums">{f.app_cambio == null ? '—' : firmado(f.app_cambio, cur)}</td>
                    <td className={`py-2 pr-2 text-right tabular-nums ${malo ? 'font-semibold' : ''}`}>
                      {f.diferencia == null ? '—' : Math.abs(f.diferencia) < 1 ? '$0' : formatCOP(Math.abs(f.diferencia), cur)}
                    </td>
                    <td className="py-2">
                      <span className={`inline-flex items-center gap-1 font-semibold ${e.clase}`}>
                        <Ico size={16} aria-hidden="true" /> {e.texto}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {problemas.length > 0 && (
        <ul className="mt-3 flex flex-col gap-3" aria-label="Qué hacer">
          {problemas.map((m) => (
            <li key={m.mes} className="rounded-xl bg-paper-raised p-3 text-xs" data-testid={`problema-${m.mes}`}>
              <p className="font-semibold text-sm">{m.etiqueta}</p>
              <p className="mt-1">{m.texto}</p>
              {m.causas?.filter((c) => c.probable && !m.texto.includes(c.texto)).map((c) => (
                <p key={c.codigo} className="mt-1 text-ink-soft">{c.texto}</p>
              ))}
              {m.acciones?.length > 0 && (
                <div className="mt-2 flex flex-col gap-2">
                  {m.acciones.map((a) => (
                    <Accion key={`${a.tipo}-${a.movimiento_id || a.historial_id}`} accion={a} moneda={cur} onHecho={hecho} ocupado={ocupado} setOcupado={setOcupado} />
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {d.impacto && <p className="mt-3 text-xs font-medium" data-testid="cuadre-impacto">{d.impacto}</p>}
      {d.saldo_corregido?.texto && <p className="mt-1 text-xs text-ink-soft" data-testid="cuadre-saldo-corregido">{d.saldo_corregido.texto}</p>}
      <p className="mt-2 text-[11px] text-ink-soft">{ORIENTACION}</p>
    </section>
  )
}
