import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDownRight, ArrowUpRight, ChevronDown, Scale } from 'lucide-react'
import { api } from '../lib/api'
import { abreviarCOP, pctTexto } from '../lib/informe'
import Ayudita from './Ayudita'
import { nombreDe } from '../lib/tituloMovimiento'

// Comparación Ingresos vs Gastos del periodo. Los números salen del servidor (regla única de
// contabilidad.py): los traslados entre tus cuentas, pagos de tarjeta y ajustes no suman ni restan.
const W = 320
const H = 150
const M = { izq: 36, der: 8, arr: 14, aba: 22 }

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

export function GraficoMeses({ meses, fmt }) {
  const valores = meses.flatMap((m) => [m.ingresos, m.gastos, m.balance])
  const max = Math.max(1, ...valores)
  const min = Math.min(0, ...valores)
  const pw = W - M.izq - M.der
  const ph = H - M.arr - M.aba
  const y = (v) => M.arr + ph - ((v - min) / (max - min)) * ph
  const g = pw / Math.max(meses.length, 1)
  const cx = (i) => M.izq + g * i + g / 2
  const ancho = Math.max(5, Math.min(14, g * 0.3))
  const resumen =
    'Ingresos, gastos y balance por mes: ' +
    meses.map((m) => `${m.etiqueta_larga}, ingresos ${fmt(m.ingresos)}, gastos ${fmt(m.gastos)}, balance ${fmt(m.balance)}`).join('; ')
  const ticks = [...new Set([min, 0, max])]
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block md:max-w-[560px] md:mx-auto" role="img" aria-label={resumen}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.izq} x2={W - M.der} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeWidth={t === 0 ? 1.2 : 0.7} strokeDasharray={t === 0 ? undefined : '2 3'} />
            <text x={M.izq - 5} y={y(t) + 3} textAnchor="end" fontSize="9" fill="var(--color-ink-soft)" style={{ fontFamily: 'var(--font-sans)' }}>
              {abreviarCOP(t)}
            </text>
          </g>
        ))}
        {meses.map((m, i) => (
          <g key={m.mes}>
            <rect x={cx(i) - ancho - 1} y={y(Math.max(m.ingresos, 0))} width={ancho} height={Math.max(Math.abs(y(0) - y(m.ingresos)), m.ingresos ? 1.5 : 0)} rx="2" fill="var(--color-cuadra)" />
            <rect x={cx(i) + 1} y={y(Math.max(m.gastos, 0))} width={ancho} height={Math.max(Math.abs(y(0) - y(m.gastos)), m.gastos ? 1.5 : 0)} rx="2" fill="var(--color-brand)" />
            <text x={cx(i)} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--color-ink-soft)" style={{ fontFamily: 'var(--font-sans)' }}>
              {m.etiqueta}
            </text>
          </g>
        ))}
        {meses.length > 1 && (
          <polyline points={meses.map((m, i) => `${cx(i)},${y(m.balance)}`).join(' ')} fill="none" stroke="var(--color-ink)" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
        )}
      </svg>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-soft mt-1" aria-label="Leyenda">
        <li className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: 'var(--color-cuadra)' }} aria-hidden="true" />Ingresos</li>
        <li className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: 'var(--color-brand)' }} aria-hidden="true" />Gastos</li>
        <li className="flex items-center gap-1.5"><span className="w-3 h-0.5" style={{ background: 'var(--color-ink)' }} aria-hidden="true" />Balance</li>
      </ul>
    </div>
  )
}

export default function IngresosGastos({ params, fmt, className = '' }) {
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
            <GraficoMeses meses={d.meses} fmt={fmt} />
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
