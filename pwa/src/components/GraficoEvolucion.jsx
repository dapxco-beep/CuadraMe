import { useEffect, useMemo, useState } from 'react'
import { LineChart, RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { abreviarCOP, escala } from '../lib/informe'
import { lecturaEvolucion, repartirEtiquetas, resumenAria, tramos } from '../lib/evolucion'
import { EsqueletoGrafica } from './Esqueletos'

// Evolución de ingresos, gastos y ahorro (ingresos - gastos) en el tiempo. Los números salen del
// servidor (GET /reportes/evolucion), que usa SOLO la regla única de contabilidad: los traslados
// entre tus cuentas y los pagos de tarjeta no suman. SVG propio y liviano, escala uniforme.
// El color nunca va solo: cada serie tiene su forma de marcador, su etiqueta directa y la tabla.
const W = 320
const H = 230
const M = { izq: 40, der: 52, arr: 14, aba: 36 }
const BASE = H - M.aba
const FUENTE = { fontFamily: 'var(--font-sans)', fontStretch: 'normal', letterSpacing: 0 }
const RANGOS = [
  { id: 6, texto: '6 meses' },
  { id: 12, texto: '12 meses' },
  { id: 0, texto: 'Todo' },
]
const VISTAS = [
  { id: 'mes', texto: 'Por mes' },
  { id: 'semana', texto: 'Por semana' },
]
const SERIES = {
  ingresos: { nombre: 'Ingresos', color: 'var(--color-cuadra)', forma: 'circulo' },
  gastos: { nombre: 'Gastos', color: 'var(--color-brand)', forma: 'cuadrado' },
  ahorro: { nombre: 'Ahorro', color: 'var(--c-serie-4)', forma: 'rombo' },
}

function Marcador({ x, y, forma, color, hueco = false, r = 3.4 }) {
  const rel = hueco
    ? { fill: 'var(--color-paper-raised)', stroke: color, strokeWidth: 1.6 }
    : { fill: color, stroke: 'var(--color-paper-raised)', strokeWidth: 1 }
  if (forma === 'cuadrado') return <rect x={x - r} y={y - r} width={r * 2} height={r * 2} rx="1" {...rel} />
  if (forma === 'rombo') {
    return <polygon points={`${x},${y - r - 1} ${x + r + 1},${y} ${x},${y + r + 1} ${x - r - 1},${y}`} {...rel} />
  }
  return <circle cx={x} cy={y} r={r} {...rel} />
}

function Boton({ activo, onClick, children }) {
  return (
    <button
      type="button"
      aria-pressed={activo}
      onClick={onClick}
      className={`px-3 min-h-[44px] rounded-full text-xs font-semibold border ${
        activo ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised text-ink-soft'
      }`}
    >
      {children}
    </button>
  )
}

export function Evolucion({ d, fmt = formatCOP, acumulado = false, vista = 'grafica' }) {
  const puntos = d.puntos
  const n = puntos.length
  const conDatos = puntos.filter((p) => p.con_datos)
  const ultimoConDato = conDatos.length ? puntos.indexOf(conDatos[conDatos.length - 1]) : null
  const [sel, setSel] = useState(null)
  const activo = sel !== null && puntos[sel] ? sel : ultimoConDato
  const muchos = n > 14 // con muchos puntos, solo línea (y marcador en el periodo activo)

  const valores = puntos.flatMap((p) =>
    p.con_datos ? [p.ingresos, p.gastos, p.ahorro, ...(acumulado ? [p.acumulado] : [])] : [],
  )
  const eje = escala(Math.min(0, ...valores), Math.max(0, ...valores))
  const pw = W - M.izq - M.der
  const ph = H - M.arr - M.aba
  const y = (v) => M.arr + ph - ((v - eje.min) / (eje.max - eje.min)) * ph
  const paso = n > 1 ? pw / (n - 1) : 0
  const x = (i) => M.izq + (n > 1 ? paso * i : pw / 2)
  const cadaK = Math.max(1, Math.ceil(n / 7))

  const lectura = useMemo(() => lecturaEvolucion(puntos, d.agrupar, fmt), [puntos, d.agrupar, fmt])

  function teclado(e) {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
    e.preventDefault()
    const dir = e.key === 'ArrowRight' ? 1 : -1
    let i = (activo ?? 0) + dir
    while (i >= 0 && i < n && !puntos[i].con_datos) i += dir
    if (i >= 0 && i < n) setSel(i)
  }

  if (vista === 'tabla') {
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <caption className="sr-only">Ingresos, gastos y ahorro por {d.agrupar === 'semana' ? 'semana' : 'mes'}</caption>
          <thead>
            <tr className="text-ink-soft text-left">
              <th scope="col" className="py-1.5 font-semibold">{d.agrupar === 'semana' ? 'Semana' : 'Mes'}</th>
              <th scope="col" className="py-1.5 font-semibold text-right">Ingresos</th>
              <th scope="col" className="py-1.5 font-semibold text-right">Gastos</th>
              <th scope="col" className="py-1.5 font-semibold text-right">Ahorro</th>
              <th scope="col" className="py-1.5 font-semibold text-right">Ahorro acumulado</th>
            </tr>
          </thead>
          <tbody>
            {puntos.map((p) => (
              <tr key={p.clave} className="border-t border-line">
                <th scope="row" className="py-2 text-left font-medium">
                  {p.etiqueta_larga}
                  {p.en_curso && <span className="block text-[11px] text-ink-soft font-normal">en curso</span>}
                </th>
                {p.con_datos ? (
                  <>
                    <td className="py-2 text-right t-cifra">{fmt(p.ingresos)}</td>
                    <td className="py-2 text-right t-cifra">{fmt(p.gastos)}</td>
                    <td className={`py-2 text-right t-cifra ${p.ahorro < 0 ? 'text-danger' : ''}`}>{fmt(p.ahorro)}</td>
                    <td className="py-2 text-right t-cifra">{fmt(p.acumulado)}</td>
                  </>
                ) : (
                  <td colSpan={4} className="py-2 text-right text-ink-soft">Sin movimientos</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  // Etiquetas directas al final de cada línea (en el último periodo con datos).
  const finales = ultimoConDato === null
    ? []
    : ['ingresos', 'gastos', 'ahorro'].map((k) => ({ k, y: y(puntos[ultimoConDato][k]), i: ultimoConDato }))
  const etiquetasFin = repartirEtiquetas(finales)
  const p = activo !== null ? puntos[activo] : null

  return (
    <div>
      <div
        tabIndex={0}
        onKeyDown={teclado}
        className="rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--color-accent)]"
        aria-label="Gráfica de evolución. Usa las flechas izquierda y derecha para ver cada periodo."
      >
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-auto block md:max-w-[620px] md:mx-auto"
          role="img"
          aria-label={resumenAria(puntos, d.agrupar, fmt)}
        >
          {eje.ticks.map((t) => (
            <g key={t}>
              <line
                x1={M.izq} x2={W - M.der} y1={y(t)} y2={y(t)}
                stroke="var(--color-line)" strokeWidth={t === 0 ? 1.2 : 0.7} strokeDasharray={t === 0 ? undefined : '2 3'}
              />
              <text x={M.izq - 5} y={y(t) + 3} textAnchor="end" fontSize="9" fill="var(--color-ink-soft)" style={FUENTE}>
                {abreviarCOP(t)}
              </text>
            </g>
          ))}

          {/* Periodos sin movimientos: franja suave (hueco), nunca un cero */}
          {puntos.map((q, i) =>
            q.con_datos ? null : (
              <rect
                key={`h-${q.clave}`} x={x(i) - Math.max(paso / 2, 4)} y={M.arr}
                width={Math.max(paso, 8)} height={ph} fill="var(--color-line)" opacity="0.35"
              />
            ),
          )}

          {activo !== null && (
            <line x1={x(activo)} x2={x(activo)} y1={M.arr} y2={BASE} stroke="var(--color-ink-soft)" strokeWidth="0.8" strokeDasharray="1 2" />
          )}

          {acumulado &&
            tramos(puntos, 'acumulado').map((t, j) => (
              <polyline
                key={`ac-${j}`} points={t.map(({ i, p: q }) => `${x(i)},${y(q.acumulado)}`).join(' ')}
                fill="none" stroke="var(--color-ink-soft)" strokeWidth="1.6" strokeDasharray="1.5 3" strokeLinecap="round"
              />
            ))}

          {['gastos', 'ingresos', 'ahorro'].map((k) =>
            tramos(puntos, k).map((t, j) => {
              const serie = SERIES[k]
              const sw = k === 'ahorro' ? 2.4 : 1.8
              const cerrados = t.filter(({ p: q }) => !q.en_curso)
              const conCurso = t.length > 1 && t[t.length - 1].p.en_curso
              const base = conCurso ? cerrados : t
              return (
                <g key={`${k}-${j}`}>
                  {base.length > 1 && (
                    <polyline
                      points={base.map(({ i, p: q }) => `${x(i)},${y(q[k])}`).join(' ')}
                      fill="none" stroke={serie.color} strokeWidth={sw} strokeLinejoin="round" strokeLinecap="round"
                    />
                  )}
                  {conCurso && (
                    <line
                      x1={x(cerrados[cerrados.length - 1].i)} y1={y(cerrados[cerrados.length - 1].p[k])}
                      x2={x(t[t.length - 1].i)} y2={y(t[t.length - 1].p[k])}
                      stroke={serie.color} strokeWidth={sw} strokeDasharray="3 3" strokeLinecap="round"
                    />
                  )}
                  {t.map(({ i, p: q }) =>
                    !muchos || t.length === 1 || i === activo ? (
                      <Marcador key={i} x={x(i)} y={y(q[k])} forma={serie.forma} color={serie.color} hueco={q.en_curso} />
                    ) : null,
                  )}
                </g>
              )
            }),
          )}

          {etiquetasFin.map((e) => (
            <text key={e.k} x={x(e.i) + 9} y={e.y + 3} fontSize="9.5" fontWeight="700" fill={SERIES[e.k].color} style={FUENTE}>
              {SERIES[e.k].nombre}
            </text>
          ))}

          {/* Eje de tiempo: meses abreviados en español */}
          {puntos.map((q, i) => {
            if (!(i % cadaK === 0 || i === n - 1 || i === activo)) return null
            const nuevoAnio = d.agrupar === 'mes' && (i === 0 || q.clave.endsWith('-01'))
            return (
              <g key={`x-${q.clave}`}>
                <text
                  x={x(i)} y={BASE + 13} textAnchor="middle" fontSize="9.5" fontWeight={i === activo ? 700 : 400}
                  fill={i === activo ? 'var(--color-ink)' : 'var(--color-ink-soft)'} style={FUENTE}
                >
                  {q.etiqueta}
                </text>
                {(q.en_curso || nuevoAnio) && (
                  <text x={x(i)} y={BASE + 23} textAnchor="middle" fontSize="8" fill="var(--color-ink-soft)" style={FUENTE}>
                    {q.en_curso ? 'en curso' : q.clave.slice(0, 4)}
                  </text>
                )}
              </g>
            )
          })}

          {/* Zonas táctiles: una columna por periodo (también los huecos) */}
          {puntos.map((q, i) => (
            <rect
              key={`t-${q.clave}`} data-testid={`punto-${q.clave}`}
              x={x(i) - Math.max(paso / 2, 6)} y={M.arr} width={Math.max(paso, 12)} height={ph + 12}
              fill="transparent" style={{ cursor: 'pointer' }} onClick={() => setSel(i)}
            />
          ))}
        </svg>
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-soft mt-1" aria-label="Leyenda">
        {Object.entries(SERIES).map(([k, s]) => (
          <li key={k} className="flex items-center gap-1.5">
            <svg width="16" height="14" viewBox="0 0 16 14" aria-hidden="true">
              <line x1="0" x2="16" y1="7" y2="7" stroke={s.color} strokeWidth="2" />
              <Marcador x={8} y={7} forma={s.forma} color={s.color} r={3} />
            </svg>
            {s.nombre}
          </li>
        ))}
        {acumulado && (
          <li className="flex items-center gap-1.5">
            <svg width="16" height="14" viewBox="0 0 16 14" aria-hidden="true">
              <line x1="0" x2="16" y1="7" y2="7" stroke="var(--color-ink-soft)" strokeWidth="2" strokeDasharray="1.5 3" strokeLinecap="round" />
            </svg>
            Ahorro acumulado
          </li>
        )}
      </ul>

      {p && (
        <div className="mt-3 rounded-2xl bg-paper border border-line px-3.5 py-3" data-testid="detalle-punto" aria-live="polite">
          <p className="text-xs font-semibold">
            {p.etiqueta_larga}
            {p.en_curso && <span className="ml-1.5 font-normal text-ink-soft">· en curso, aún no termina</span>}
          </p>
          {p.con_datos ? (
            <dl className="grid grid-cols-3 gap-2 mt-2">
              <div>
                <dt className="text-[11px] text-ink-soft">Ingresos</dt>
                <dd className="text-sm font-bold t-cifra">{fmt(p.ingresos)}</dd>
              </div>
              <div>
                <dt className="text-[11px] text-ink-soft">Gastos</dt>
                <dd className="text-sm font-bold t-cifra">{fmt(p.gastos)}</dd>
              </div>
              <div>
                <dt className="text-[11px] text-ink-soft">Ahorro</dt>
                <dd className={`text-sm font-bold t-cifra ${p.ahorro < 0 ? 'text-danger' : 'text-accent'}`}>{fmt(p.ahorro)}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-xs text-ink-soft mt-1">Sin movimientos en este periodo.</p>
          )}
        </div>
      )}

      {lectura.length > 0 && (
        <div className="mt-3 space-y-1" data-testid="lectura-evolucion">
          {lectura.map((f) => (
            <p key={f} className="text-sm leading-relaxed">{f}</p>
          ))}
        </div>
      )}
    </div>
  )
}

export default function GraficoEvolucion({ fmt = formatCOP, className = '' }) {
  const [meses, setMeses] = useState(6)
  const [agrupar, setAgrupar] = useState('mes')
  const [acumulado, setAcumulado] = useState(false)
  const [tabla, setTabla] = useState(false)
  const [d, setD] = useState(null)
  const [error, setError] = useState(false)
  const [intento, setIntento] = useState(0)

  useEffect(() => {
    let vivo = true
    setError(false)
    Promise.resolve()
      .then(() => api.evolucion({ agrupar, meses }))
      .then((r) => vivo && setD(r))
      .catch(() => vivo && setError(true))
    return () => {
      vivo = false
    }
  }, [agrupar, meses, intento])

  const pocos = d && d.meses_con_datos < 2
  return (
    <section
      id="evolucion"
      className={`card-marca bg-paper-raised border border-line p-4 scroll-mt-4 ${className}`}
      aria-label="Evolución de tus ingresos, gastos y ahorro"
    >
      <div className="flex items-center gap-2 mb-1">
        <LineChart size={16} className="text-ink-soft" aria-hidden="true" />
        <h2 className="text-[15px] font-semibold">Mi evolución</h2>
      </div>
      <p className="text-xs text-ink-soft mb-3">Ingresos, gastos y ahorro (lo que te queda de lo que entra) en el tiempo.</p>

      <div className="flex flex-wrap gap-x-4 gap-y-1 mb-2">
        <div className="flex gap-1.5" role="group" aria-label="Cuánto tiempo mirar">
          {RANGOS.map((r) => (
            <Boton key={r.id} activo={meses === r.id} onClick={() => setMeses(r.id)}>{r.texto}</Boton>
          ))}
        </div>
        <div className="flex gap-1.5" role="group" aria-label="Agrupar">
          {VISTAS.map((v) => (
            <Boton key={v.id} activo={agrupar === v.id} onClick={() => setAgrupar(v.id)}>{v.texto}</Boton>
          ))}
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-2xl bg-paper border border-line px-4 py-6 text-center">
          <p className="text-sm font-semibold">No pudimos cargar tu evolución</p>
          <p className="text-xs text-ink-soft mt-1">Revisa tu conexión e intenta de nuevo.</p>
          <button
            type="button" onClick={() => setIntento((i) => i + 1)}
            className="mt-2 min-h-[44px] px-3 text-sm font-semibold text-accent inline-flex items-center gap-1"
          >
            <RefreshCw size={16} aria-hidden="true" /> Reintentar
          </button>
        </div>
      )}
      {!error && !d && <EsqueletoGrafica alto={200} etiqueta="Cargando tu evolución" />}
      {!error && d && pocos && (
        <div className="rounded-2xl bg-paper border border-line px-4 py-8 text-center">
          <LineChart size={24} className="mx-auto text-ink-soft" aria-hidden="true" />
          <p className="text-sm font-semibold mt-2">Aquí verás cómo cambia tu plata</p>
          <p className="text-xs text-ink-soft mt-1">Cuando tengas movimientos de al menos 2 meses verás tu evolución.</p>
        </div>
      )}
      {!error && d && !pocos && (
        <>
          <Evolucion key={`${d.agrupar}-${d.meses}`} d={d} fmt={fmt} acumulado={acumulado} vista={tabla ? 'tabla' : 'grafica'} />
          <div className="flex flex-wrap items-center justify-between gap-2 mt-2">
            <label className="flex items-center gap-2 text-xs text-ink-soft min-h-[44px]">
              <input type="checkbox" checked={acumulado} onChange={(e) => setAcumulado(e.target.checked)} />
              Ver ahorro acumulado
            </label>
            <button
              type="button" aria-pressed={tabla} onClick={() => setTabla((t) => !t)}
              className="text-sm font-semibold text-accent min-h-[44px] px-2"
            >
              {tabla ? 'Ver gráfica' : 'Ver como tabla'}
            </button>
          </div>
          <p className="text-[11px] text-ink-soft">No incluye traslados entre tus cuentas ni pagos de tarjeta.</p>
        </>
      )}
    </section>
  )
}
