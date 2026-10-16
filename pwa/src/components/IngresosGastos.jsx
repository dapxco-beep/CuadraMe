import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDownRight, ArrowUpRight, ChevronDown, Scale } from 'lucide-react'
import { api } from '../lib/api'
import { pctTexto } from '../lib/informe'
import GraficoMeses from './GraficoMeses'
import Ayudita from './Ayudita'
import { nombreDe } from '../lib/tituloMovimiento'

// Comparación Ingresos vs Gastos del periodo. Los números salen del servidor (regla única de
// contabilidad.py): los traslados entre tus cuentas, pagos de tarjeta y ajustes no suman ni restan.
function Cambio({ pct, mejorSube }) {
  if (pct === null || pct === undefined) return <span className="text-[11px] text-ink-soft">sin base para comparar</span>
  const Icono = pct >= 0 ? ArrowUpRight : ArrowDownRight
  const bueno = pct === 0 ? null : pct > 0 === mejorSube
  return (
    <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${bueno === null ? 'text-ink-soft' : bueno ? 'text-cuadra' : 'text-danger'}`}>
      {pct !== 0 && <Icono size={16} aria-hidden="true" />}
      {pctTexto(pct)}
    </span>
  )
}

export { GraficoMeses }

export default function IngresosGastos({ params, fmt, className = '', seleccion = null, onSeleccion }) {
  const [d, setD] = useState(null)
  const [noCuenta, setNoCuenta] = useState(null)
  const [abierto, setAbierto] = useState(false)

  useEffect(() => {
    let activo = true
    setAbierto(false)
    setNoCuenta(null)
    Promise.resolve()
      .then(() => api.ingresosGastos({ ...params, meses: 6 }))
      .then((r) => activo && setD(r))
      .catch(() => activo && setD(null))
    return () => {
      activo = false
    }
  }, [params])

  function verNoCuenta() {
    const abre = !abierto
    setAbierto(abre)
    if (abre && !noCuenta) {
      Promise.resolve()
        .then(() => api.informeNoSeCuenta(params))
        .then(setNoCuenta)
        .catch(() => setNoCuenta({ error: true, movimientos: [], grupos: [], cantidad: 0 }))
    }
  }

  if (!d) return null
  const signo = d.balance > 0 ? '+' : d.balance < 0 ? '-' : ''
  const colorBalance = d.balance > 0 ? 'text-accent' : d.balance < 0 ? 'text-danger' : 'text-ink'
  return (
    <section className={`card-marca bg-paper-raised border border-line p-4 ${className}`} aria-label="Ingresos contra gastos">
      <div className="flex items-center gap-2 mb-3">
        <Scale size={16} className="text-ink-soft" aria-hidden="true" />
        <h2 className="text-[15px] font-semibold">Ingresos y gastos</h2>
      </div>
      {!d.hay_datos ? (
        <p className="text-sm text-ink-soft">Cuando registres ingresos y gastos, aquí verás cuánto te queda cada mes.</p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-3">
            <div>
              <dt className="text-xs text-ink-soft">Ingresos</dt>
              <dd className="text-lg font-bold text-accent t-cifra">{fmt(d.ingresos)}</dd>
              <Cambio pct={d.variacion.ingresos_pct} mejorSube />
            </div>
            <div>
              <dt className="text-xs text-ink-soft">Gastos</dt>
              <dd className="text-lg font-bold text-ink t-cifra">{fmt(d.gastos)}</dd>
              <Cambio pct={d.variacion.gastos_pct} mejorSube={false} />
            </div>
            <div>
              <dt className="text-xs text-ink-soft">Balance</dt>
              <dd className={`text-lg font-bold t-cifra ${colorBalance}`}>{signo}{fmt(Math.abs(d.balance))}</dd>
              <Cambio pct={d.variacion.balance_pct} mejorSube />
            </div>
            <div>
              <dt className="text-xs text-ink-soft">Tasa de ahorro</dt>
              <dd className="text-lg font-bold t-cifra">{d.tasa_ahorro === null ? '—' : `${String(d.tasa_ahorro).replace('.', ',')} %`}</dd>
              {d.tasa_ahorro === null && <span className="text-[11px] text-ink-soft">Sin ingresos en el periodo</span>}
            </div>
          </dl>
          <p className="text-[11px] text-ink-soft mt-2">
            Frente a {d.anterior.etiqueta}: ingresos {fmt(d.anterior.ingresos)}, gastos {fmt(d.anterior.gastos)}
          </p>
          <div className="mt-4">
            <GraficoMeses meses={d.meses} fmt={fmt} seleccion={seleccion} onSeleccion={onSeleccion} />
          </div>
        </>
      )}
      <p className="text-xs text-ink-soft mt-3">
        No incluye traslados entre tus cuentas ni pagos de tarjeta. <Ayudita termino="traslado" />
      </p>
      <button type="button" onClick={verNoCuenta} aria-expanded={abierto} className="mt-1 text-sm font-semibold text-accent min-h-[44px] inline-flex items-center gap-1">
        Ver lo que no se cuenta
        <ChevronDown size={16} className={abierto ? 'rotate-180' : ''} aria-hidden="true" />
      </button>
      {abierto && (
        <div className="mt-1">
          {!noCuenta && <p className="text-xs text-ink-soft">Cargando…</p>}
          {noCuenta?.error && <p role="alert" className="text-xs text-danger">No pudimos cargarlo. Revisa tu conexión e intenta de nuevo.</p>}
          {noCuenta && !noCuenta.error && noCuenta.cantidad === 0 && <p className="text-xs text-ink-soft">No hay nada fuera de la cuenta en este periodo.</p>}
          {noCuenta && !noCuenta.error && noCuenta.cantidad > 0 && (
            <>
              <p className="text-xs text-ink-soft mb-1">{noCuenta.grupos.map((g) => `${g.nombre}: ${g.cantidad}`).join(' · ')}</p>
              <ul className="divide-y divide-line" aria-label="Movimientos que no se cuentan">
                {noCuenta.movimientos.map((m) => (
                  <li key={m.id}>
                    <Link to={`/movimientos/${m.id}`} className="flex items-center justify-between gap-3 py-2 text-xs min-h-[44px]">
                      <span className="min-w-0">
                        <span className="block font-medium truncate">{nombreDe(m)}</span>
                        <span className="text-ink-soft">{m.fecha.slice(0, 10)} · {m.motivo}</span>
                      </span>
                      <span className="font-semibold shrink-0">{fmt(m.monto)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
              {noCuenta.truncado && <p className="text-[11px] text-ink-soft mt-1">Se muestran los más recientes.</p>}
            </>
          )}
        </div>
      )}
    </section>
  )
}
