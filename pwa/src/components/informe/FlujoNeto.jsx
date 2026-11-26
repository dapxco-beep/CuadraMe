import { useEffect, useId, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Waves } from 'lucide-react'
import { abreviarEje, curvaSuave, escalaBonita, rutaBarra } from '../../lib/graficos'
import { useLectura } from '../../lib/useLectura'
import Lectura from '../Lectura'
import { Chip } from '../ui'
import { Panel, conSigno } from './comun'

// Flujo neto = ingresos − gastos de cada día, semana o mes DENTRO del periodo elegido. Responde: «¿en qué momentos me
// sobró plata y en cuáles me faltó?». Los números salen del servidor (informe_resumen.flujo_neto, regla única de
// contabilidad). Un tramo sin movimientos queda en blanco (hueco), no como un cero engañoso. Los tramos negativos van
// rayados además de rojos: el color nunca es la única señal.
const W = 320
const H = 200
const M = { izq: 46, der: 8, arr: 10, aba: 24 }
const FUENTE = { fontFamily: 'var(--font-sans)' }
const AGRUPACIONES = [
  { id: 'dia', texto: 'Día' },
  { id: 'semana', texto: 'Semana' },
  { id: 'mes', texto: 'Mes' },
]
const AYUDA =
  'Flujo neto = lo que entró menos lo que salió en cada tramo. Barra hacia arriba: te sobró plata; barra rayada hacia abajo: ' +
  'gastaste más de lo que entró. «Acumulado» suma los tramos uno tras otro, así ves si en total vas ganando o perdiendo. ' +
  'No cuenta traslados entre tus cuentas ni pagos de tarjeta.'

export default function FlujoNeto({ flujo, fmt, agrupar, onAgrupar }) {
  const gid = useId()
  const [vista, setVista] = useState('periodo')
  const [sel, setSel] = useState(null)
  const puntos = flujo.puntos
  const n = puntos.length
  useEffect(() => setSel(null), [flujo])

  const pw = W - M.izq - M.der
  const ph = H - M.arr - M.aba
  const g = pw / Math.max(n, 1)
  const x = (i) => M.izq + g * i + g / 2
  const valor = (p) => (vista === 'periodo' ? p.neto : p.acumulado)
  const { min, max, ticks } = useMemo(() => {
    const vals = puntos.map(valor).filter((v) => v !== null && v !== undefined)
    return escalaBonita(Math.min(0, ...vals), Math.max(0, ...vals))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [puntos, vista])
  const y = (v) => M.arr + ph - ((v - min) / (max - min || 1)) * ph
  const y0 = y(0)
  const ancho = Math.max(2, Math.min(22, g * 0.68))
  const paso = Math.ceil(n / 7)

  const { ref, activo, manejadores } = useLectura({ n, W, xDe: x, onElegir: (i) => setSel((s) => (s === i ? null : i)) })
  const mAct = activo !== null ? puntos[activo] : null
  const enfoque = activo ?? sel
  const elegido = sel !== null ? puntos[sel] : null
  const filasDe = (p) =>
    p.con_datos
      ? [
          { nombre: 'Ingresos', valor: fmt(p.ingresos), color: 'var(--color-cuadra)' },
          { nombre: 'Gastos', valor: fmt(p.gastos), color: 'var(--color-brand)' },
          { nombre: 'Flujo neto', valor: conSigno(p.neto, fmt), clase: p.neto < 0 ? 'text-danger' : 'text-ink' },
          { nombre: 'Acumulado', valor: conSigno(p.acumulado, fmt) },
        ]
      : [{ nombre: 'Sin movimientos', valor: '' }]

  const lineaAcum = vista === 'acumulado' ? curvaSuave(puntos.map((p, i) => [x(i), y(p.acumulado)])) : ''
  const resumenAria =
    `Flujo neto por ${agrupar === 'dia' ? 'día' : agrupar === 'semana' ? 'semana' : 'mes'}: ` +
    puntos.filter((p) => p.con_datos).map((p) => `${p.etiqueta_larga}, ${conSigno(p.neto, fmt)}`).join('; ')
  const porClave = (c) => puntos.find((p) => p.clave === c)
  const mejor = porClave(flujo.mejor)
  const peor = porClave(flujo.peor)
  const final = puntos.length ? puntos[puntos.length - 1].acumulado : 0

  return (
    <Panel
      icono={Waves}
      titulo="Flujo neto"
      pregunta="¿En qué momentos te sobró plata y en cuáles te faltó?"
      info={AYUDA}
    >
      {!flujo.hay_datos ? (
        <p className="text-sm text-ink-soft">No hay ingresos ni gastos en este periodo. Cuando los haya, aquí verás cómo se movió tu plata.</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <div role="group" aria-label="Agrupar por" className="flex gap-1.5">
              {AGRUPACIONES.map((a) => (
                <Chip key={a.id} activo={agrupar === a.id} onClick={() => onAgrupar(a.id)} className="text-xs font-semibold">
                  {a.texto}
                </Chip>
              ))}
            </div>
            <div role="group" aria-label="Qué mostrar" className="flex rounded-full bg-paper border border-line p-0.5 ml-auto">
              {[['periodo', 'Cada tramo'], ['acumulado', 'Acumulado']].map(([id, texto]) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={vista === id}
                  onClick={() => setVista(id)}
                  className={`px-3 min-h-[44px] rounded-full text-xs font-semibold ${vista === id ? 'bg-accent text-paper-raised' : 'text-ink-soft'}`}
                >
                  {texto}
                </button>
              ))}
            </div>
          </div>

          <div className="lg:grid lg:grid-cols-[minmax(0,540px)_minmax(0,1fr)] lg:gap-8 lg:items-start">
          <div
            {...manejadores}
            ref={ref}
            tabIndex={0}
            role="group"
            aria-roledescription="gráfico interactivo"
            aria-label="Gráfico del flujo neto. Con las flechas izquierda y derecha recorres los tramos; Enter selecciona uno para ver sus movimientos."
            className="gr-lienzo relative mt-2 md:max-w-[540px] md:mx-auto lg:mx-0"
          >
            {mAct && <Lectura pct={(x(activo) / W) * 100} titulo={mAct.etiqueta_larga} filas={filasDe(mAct)} />}
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block" role="img" aria-label={resumenAria}>
              <defs>
                <pattern id={`${gid}-rayas`} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="5" height="5" fill="var(--color-danger-soft)" />
                  <line x1="0" y1="0" x2="0" y2="5" stroke="var(--color-danger)" strokeWidth="2.2" />
                </pattern>
                <linearGradient id={`${gid}-pos`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="var(--color-cuadra)" stopOpacity="1" />
                  <stop offset="1" stopColor="var(--color-cuadra)" stopOpacity="0.62" />
                </linearGradient>
                <linearGradient id={`${gid}-area`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="var(--color-ink)" stopOpacity="0.14" />
                  <stop offset="1" stopColor="var(--color-ink)" stopOpacity="0" />
                </linearGradient>
              </defs>
              {ticks.map((t) => (
                <g key={t}>
                  <line x1={M.izq} x2={W - M.der} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeOpacity={t === 0 ? 1 : 0.55} strokeWidth={t === 0 ? 1 : 0.6} />
                  <text x={M.izq - 6} y={y(t) + 3} textAnchor="end" fontSize="11" fill="var(--color-ink-soft)" style={FUENTE}>{abreviarEje(t)}</text>
                </g>
              ))}
              {enfoque !== null && (
                <rect x={M.izq + g * enfoque + 0.5} y={M.arr} width={Math.max(g - 1, 2)} height={ph} rx="4" fill="var(--color-ink)" opacity={activo !== null ? 0.07 : 0.045} />
              )}
              {vista === 'periodo' &&
                puntos.map((p, i) => {
                  if (!p.con_datos || p.neto === 0) return null
                  const xi = x(i) - ancho / 2
                  return p.neto > 0 ? (
                    <path key={p.clave} className="gr-barra" style={{ '--i': i }} d={rutaBarra(xi, y(p.neto), ancho, y0, Math.min(4, ancho / 2))} fill={`url(#${gid}-pos)`} />
                  ) : (
                    <rect key={p.clave} className="gr-barra" style={{ '--i': i }} x={xi} y={y0} width={ancho} height={Math.max(y(p.neto) - y0, 1)} rx="2" fill={`url(#${gid}-rayas)`} stroke="var(--color-danger)" strokeWidth="0.8" />
                  )
                })}
              {vista === 'acumulado' && n > 1 && (
                <g className="gr-aparece">
                  <path d={`${lineaAcum}L${x(n - 1)},${y0}L${x(0)},${y0}Z`} fill={`url(#${gid}-area)`} />
                  <path className="gr-linea" pathLength="1" d={lineaAcum} fill="none" stroke="var(--color-ink)" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
                </g>
              )}
              {vista === 'acumulado' && enfoque !== null && (
                <circle cx={x(enfoque)} cy={y(puntos[enfoque].acumulado)} r="3.6" fill="var(--color-paper-raised)" stroke="var(--color-ink)" strokeWidth="1.8" />
              )}
              {puntos.map((p, i) =>
                i % paso === 0 ? (
                  <text key={p.clave} x={x(i)} y={H - 7} textAnchor="middle" fontSize="11" fontWeight={i === sel ? 700 : 400} fill={i === sel ? 'var(--color-ink)' : 'var(--color-ink-soft)'} style={FUENTE}>
                    {p.etiqueta}
                  </text>
                ) : null
              )}
            </svg>
            <p className="sr-only" aria-live="polite" role="status">
              {mAct ? `${mAct.etiqueta_larga}: ${mAct.con_datos ? `ingresos ${fmt(mAct.ingresos)}, gastos ${fmt(mAct.gastos)}, flujo neto ${conSigno(mAct.neto, fmt)}` : 'sin movimientos'}.` : ''}
            </p>
          </div>

          <div className="min-w-0 lg:pt-3">
          {elegido ? (
            <div className="mt-2 rounded-xl bg-paper border border-line p-3 text-xs" data-testid="flujo-detalle">
              <p className="font-semibold first-letter:uppercase">{elegido.etiqueta_larga}</p>
              {elegido.con_datos ? (
                <p className="mt-0.5 text-ink-soft">
                  Entró {fmt(elegido.ingresos)} · salió {fmt(elegido.gastos)} · flujo neto <b className={elegido.neto < 0 ? 'text-danger' : 'text-ink'}>{conSigno(elegido.neto, fmt)}</b>
                </p>
              ) : (
                <p className="mt-0.5 text-ink-soft">Sin movimientos en este tramo.</p>
              )}
              {elegido.con_datos && (
                <Link to={`/movimientos?desde=${elegido.desde}&hasta=${elegido.hasta}`} className="inline-flex items-center min-h-11 font-semibold text-accent">
                  Ver los movimientos de este tramo
                </Link>
              )}
            </div>
          ) : (
            <p className="mt-2 text-xs text-ink-soft leading-relaxed">
              {flujo.positivos} {flujo.positivos === 1 ? 'tramo' : 'tramos'} con plata sobrante y {flujo.negativos} con plata faltante.
              {mejor && ` Tu mejor tramo: ${mejor.etiqueta_larga} (${conSigno(mejor.neto, fmt)}).`}
              {peor && peor.clave !== mejor?.clave && peor.neto < 0 && ` El más ajustado: ${peor.etiqueta_larga} (${conSigno(peor.neto, fmt)}).`}
              {` En total: ${conSigno(final, fmt)}. Toca una barra para ver sus movimientos.`}
            </p>
          )}

          </div>
          </div>

          <div className="sr-only">
            <table>
              <caption>Flujo neto por tramo</caption>
              <thead><tr><th>Tramo</th><th>Ingresos</th><th>Gastos</th><th>Flujo neto</th></tr></thead>
              <tbody>
                {puntos.filter((p) => p.con_datos).map((p) => (
                  <tr key={p.clave}><th scope="row">{p.etiqueta_larga}</th><td>{fmt(p.ingresos)} pesos</td><td>{fmt(p.gastos)} pesos</td><td>{conSigno(p.neto, fmt)} pesos</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  )
}
