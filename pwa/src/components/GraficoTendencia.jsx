import { useMemo, useState } from 'react'
import { BarChart3 } from 'lucide-react'
import { formatCOP } from '../lib/format'
import { abreviarCOP, escala, etiquetaMesCorta, nombreMesLargo, seleccionarMeses, tieneDatos } from '../lib/informe'

// Gráfica de ingresos vs gastos por mes (barras agrupadas finas), con línea de
// ahorro neto opcional. SVG con viewBox fijo y escala UNIFORME (nada se estira),
// texto en Sora normal, eje Y con cuadrícula sutil, valores abreviados, toque para
// ver el detalle, y una tabla equivalente para lectores de pantalla.
const W = 320
const H = 200
const M = { izq: 40, der: 10, arr: 16, aba: 24 }
const RANGOS = [3, 6, 12]
const FUENTE = { fontFamily: 'var(--font-sans)', fontStretch: 'normal', letterSpacing: 0 }

export default function GraficoTendencia({ meses = [], rangoInicial = 6 }) {
  const [n, setN] = useState(rangoInicial)
  const [vacios, setVacios] = useState(false)
  const [ahorro, setAhorro] = useState(false)
  const [tabla, setTabla] = useState(false)
  const [sel, setSel] = useState(null)

  const visibles = useMemo(() => seleccionarMeses(meses, n, vacios), [meses, n, vacios])
  const conDatos = visibles.filter(tieneDatos)
  const k = visibles.length

  const valores = visibles.flatMap((m) => [m.ingresos, m.gastos, ...(ahorro ? [m.ahorro] : [])])
  const eje = escala(Math.min(0, ...valores), Math.max(0, ...valores))
  const pw = W - M.izq - M.der
  const ph = H - M.arr - M.aba
  const y = (v) => M.arr + ph - ((v - eje.min) / (eje.max - eje.min)) * ph
  const grupo = k ? pw / k : pw
  const ancho = Math.max(4, Math.min(11, grupo * 0.26))
  const cx = (i) => M.izq + grupo * i + grupo / 2
  const etiquetasValor = k <= 4

  const resumenAria = `Ingresos y gastos de ${k} ${k === 1 ? 'mes' : 'meses'}: ` +
    visibles.map((m) => `${nombreMesLargo(m.mes)}, ingresos ${formatCOP(m.ingresos)}, gastos ${formatCOP(m.gastos)}`).join('; ')

  const activo = sel !== null && visibles[sel] ? sel : null

  return (
    <div>
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex gap-1.5" role="group" aria-label="Meses a mostrar">
          {RANGOS.map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={n === r}
              onClick={() => { setN(r); setSel(null) }}
              className={`px-3 min-h-[34px] rounded-full text-xs font-semibold border ${
                n === r ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised text-ink-soft'
              }`}
            >
              {r} meses
            </button>
          ))}
        </div>
        <button
          type="button"
          aria-pressed={tabla}
          onClick={() => setTabla((t) => !t)}
          className="text-xs font-semibold text-accent min-h-[34px] px-2"
        >
          {tabla ? 'Ver gráfica' : 'Ver tabla'}
        </button>
      </div>

      {conDatos.length === 0 ? (
        <div className="rounded-2xl bg-paper border border-line px-4 py-8 text-center">
          <BarChart3 size={26} className="mx-auto text-ink-soft" aria-hidden="true" />
          <p className="text-sm font-semibold mt-2">Aún no hay movimientos en estos meses</p>
          <p className="text-xs text-ink-soft mt-1">Cuando registres ingresos y gastos, aquí verás cómo evoluciona tu plata mes a mes.</p>
        </div>
      ) : tabla ? (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <caption className="sr-only">Ingresos, gastos y ahorro por mes</caption>
            <thead>
              <tr className="text-ink-soft text-left">
                <th scope="col" className="py-1.5 font-semibold">Mes</th>
                <th scope="col" className="py-1.5 font-semibold text-right">Ingresos</th>
                <th scope="col" className="py-1.5 font-semibold text-right">Gastos</th>
                <th scope="col" className="py-1.5 font-semibold text-right">Ahorro</th>
              </tr>
            </thead>
            <tbody>
              {visibles.map((m) => (
                <tr key={m.mes} className={`border-t border-line ${tieneDatos(m) ? '' : 'opacity-50'}`}>
                  <th scope="row" className="py-2 text-left font-medium">{nombreMesLargo(m.mes)}</th>
                  <td className="py-2 text-right">{formatCOP(m.ingresos)}</td>
                  <td className="py-2 text-right">{formatCOP(m.gastos)}</td>
                  <td className={`py-2 text-right ${m.ahorro < 0 ? 'text-danger' : ''}`}>{formatCOP(m.ahorro)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block md:max-w-[560px] md:mx-auto" role="img" aria-label={resumenAria}>
            {eje.ticks.map((t) => (
              <g key={t}>
                <line x1={M.izq} x2={W - M.der} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeWidth={t === 0 ? 1.2 : 0.7} strokeDasharray={t === 0 ? undefined : '2 3'} />
                <text x={M.izq - 6} y={y(t) + 3} textAnchor="end" fontSize="9" fill="var(--color-ink-soft)" style={FUENTE}>
                  {abreviarCOP(t)}
                </text>
              </g>
            ))}

            {visibles.map((m, i) => {
              const vacio = !tieneDatos(m)
              const atenuado = vacio || (activo !== null && activo !== i)
              const base = y(0)
              const hi = Math.max(base - y(m.ingresos), m.ingresos > 0 ? 1.5 : 0)
              const hg = Math.max(base - y(m.gastos), m.gastos > 0 ? 1.5 : 0)
              return (
                <g key={m.mes} opacity={atenuado ? (vacio ? 0.45 : 0.4) : 1}>
                  <rect x={cx(i) - ancho - 1} y={base - hi} width={ancho} height={hi} rx={Math.min(3, ancho / 2)} fill="var(--color-cuadra)" />
                  <rect x={cx(i) + 1} y={base - hg} width={ancho} height={hg} rx={Math.min(3, ancho / 2)} fill="var(--color-brand)" />
                  {(etiquetasValor || activo === i) && !vacio && (
                    <>
                      {m.ingresos > 0 && (
                        <text x={cx(i) - ancho / 2 - 1} y={base - hi - 3} textAnchor="middle" fontSize="8.5" fill="var(--color-ink)" style={FUENTE}>
                          {abreviarCOP(m.ingresos)}
                        </text>
                      )}
                      {m.gastos > 0 && (
                        <text x={cx(i) + ancho / 2 + 1} y={base - hg - 3} textAnchor="middle" fontSize="8.5" fill="var(--color-ink)" style={FUENTE}>
                          {abreviarCOP(m.gastos)}
                        </text>
                      )}
                    </>
                  )}
                  <text x={cx(i)} y={H - 7} textAnchor="middle" fontSize="10" fill="var(--color-ink-soft)" style={{ ...FUENTE, fontWeight: activo === i ? 700 : 400 }}>
                    {etiquetaMesCorta(m.mes)}
                  </text>
                </g>
              )
            })}

            {ahorro && k > 0 && (
              <g>
                {k > 1 && (
                  <polyline
                    points={visibles.map((m, i) => `${cx(i)},${y(m.ahorro)}`).join(' ')}
                    fill="none" stroke="var(--color-ink)" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round"
                  />
                )}
                {visibles.map((m, i) => (
                  <circle key={m.mes} cx={cx(i)} cy={y(m.ahorro)} r="2.6" fill="var(--color-paper-raised)" stroke="var(--color-ink)" strokeWidth="1.5" />
                ))}
              </g>
            )}

            {visibles.map((m, i) => (
              <rect
                key={`t-${m.mes}`}
                x={M.izq + grupo * i}
                y={M.arr}
                width={grupo}
                height={ph + M.aba}
                fill="transparent"
                tabIndex={0}
                role="button"
                aria-label={`${nombreMesLargo(m.mes)}: ingresos ${formatCOP(m.ingresos)}, gastos ${formatCOP(m.gastos)}, ahorro ${formatCOP(m.ahorro)}`}
                onClick={() => setSel(activo === i ? null : i)}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setSel(activo === i ? null : i))}
                style={{ cursor: 'pointer', outline: 'none' }}
              />
            ))}
          </svg>

          {activo !== null && (
            <div
              className="absolute top-0 pointer-events-none"
              style={{ left: `${Math.min(Math.max(((cx(activo)) / W) * 100, 24), 76)}%`, transform: 'translateX(-50%)' }}
            >
              <div className="bg-ink text-paper text-[11px] rounded-xl px-3 py-2 shadow-lg whitespace-nowrap">
                <p className="font-semibold">{nombreMesLargo(visibles[activo].mes)}</p>
                <p>Ingresos {formatCOP(visibles[activo].ingresos)}</p>
                <p>Gastos {formatCOP(visibles[activo].gastos)}</p>
                <p>Ahorro {formatCOP(visibles[activo].ahorro)}</p>
              </div>
            </div>
          )}

          <div className="flex items-center gap-4 mt-2 justify-center flex-wrap">
            <span className="flex items-center gap-1.5 text-xs text-ink-soft">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'var(--color-cuadra)' }} /> Ingresos
            </span>
            <span className="flex items-center gap-1.5 text-xs text-ink-soft">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'var(--color-brand)' }} /> Gastos
            </span>
            {ahorro && (
              <span className="flex items-center gap-1.5 text-xs text-ink-soft">
                <span className="w-3.5 h-0.5 bg-ink" /> Ahorro neto
              </span>
            )}
          </div>
          {conDatos.length === 1 && (
            <p className="text-xs text-ink-soft text-center mt-2">
              Solo hay un mes con datos: la tendencia aparece cuando tengas al menos dos.
            </p>
          )}
        </div>
      )}

      <div className="flex gap-4 mt-3 flex-wrap">
        <label className="flex items-center gap-2 text-xs text-ink-soft min-h-[32px]">
          <input type="checkbox" checked={ahorro} onChange={(e) => setAhorro(e.target.checked)} /> Mostrar ahorro neto
        </label>
        <label className="flex items-center gap-2 text-xs text-ink-soft min-h-[32px]">
          <input type="checkbox" checked={vacios} onChange={(e) => setVacios(e.target.checked)} /> Mostrar meses sin datos
        </label>
      </div>
    </div>
  )
}
