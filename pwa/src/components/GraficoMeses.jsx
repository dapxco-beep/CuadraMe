import { useCallback, useId, useMemo, useState } from 'react'
import { abreviarEje, curvaSuave, escalaBonita, rutaBarra } from '../lib/graficos'
import { pctTexto } from '../lib/informe'
import { useLectura } from '../lib/useLectura'
import Lectura from './Lectura'

// Ingresos, gastos y balance por mes. Gráfico propio en SVG (sin librerías): barras redondeadas con degradado,
// balance como curva suave con área tenue, rejilla sutil y ejes cortos. Interactivo: tocar/arrastrar muestra la
// lectura del mes, tocar una barra la selecciona (el resto del informe se enfoca en ese mes), la leyenda
// muestra/oculta series y se maneja con teclado (←/→, Enter, Esc). Los números vienen del servidor.
const W = 320
const H = 196
const M = { izq: 42, der: 8, arr: 8, aba: 22 }
const FUENTE = { fontFamily: 'var(--font-sans)' }
const SERIES = [
  { id: 'ingresos', nombre: 'Ingresos', color: 'var(--color-cuadra)' },
  { id: 'gastos', nombre: 'Gastos', color: 'var(--color-brand)' },
  { id: 'balance', nombre: 'Balance', color: 'var(--color-ink)' },
]

function textoVar(pct) {
  if (pct === null || pct === undefined) return 'sin base'
  if (pct === 0) return 'igual'
  return `${pct > 0 ? '↑' : '↓'} ${pctTexto(Math.abs(pct)).replace('+', '')}`
}

export default function GraficoMeses({ meses, fmt, seleccion = null, onSeleccion }) {
  const gid = useId()
  const [ocultas, setOcultas] = useState([])
  const visible = (id) => !ocultas.includes(id)
  const pw = W - M.izq - M.der
  const ph = H - M.arr - M.aba
  const g = pw / Math.max(meses.length, 1)
  const cx = useCallback((i) => M.izq + g * i + g / 2, [g])

  const { min, max, ticks } = useMemo(() => {
    const vals = meses.flatMap((m) => SERIES.filter((s) => !ocultas.includes(s.id)).map((s) => m[s.id]))
    return escalaBonita(Math.min(0, ...vals), Math.max(0, ...vals))
  }, [meses, ocultas])
  const y = (v) => M.arr + ph - ((v - min) / (max - min || 1)) * ph
  const y0 = y(0)
  const ancho = Math.max(5, Math.min(15, g * 0.34))

  const elegir = (i) => onSeleccion && onSeleccion(seleccion === meses[i].mes ? null : meses[i].mes)
  const { ref, activo, manejadores } = useLectura({ n: meses.length, W, xDe: cx, onElegir: elegir })

  const resumen =
    'Ingresos, gastos y balance por mes: ' +
    meses.map((m) => `${m.etiqueta_larga}, ingresos ${fmt(m.ingresos)}, gastos ${fmt(m.gastos)}, balance ${fmt(m.balance)}`).join('; ')

  const puntos = meses.map((m, i) => [cx(i), y(m.balance)])
  const trazo = curvaSuave(puntos)
  const area = meses.length > 1 ? `${trazo}L${puntos[puntos.length - 1][0]},${y0}L${puntos[0][0]},${y0}Z` : ''
  const iSel = seleccion ? meses.findIndex((m) => m.mes === seleccion) : -1
  const enfoque = activo ?? (iSel >= 0 ? iSel : null)
  const mAct = activo !== null ? meses[activo] : null
  const filas = mAct && [
    ...(visible('ingresos') ? [{ nombre: 'Ingresos', valor: fmt(mAct.ingresos), color: SERIES[0].color }] : []),
    ...(visible('gastos') ? [{ nombre: 'Gastos', valor: fmt(mAct.gastos), color: SERIES[1].color }] : []),
    ...(visible('balance') ? [{ nombre: 'Balance', valor: `${mAct.balance < 0 ? '-' : ''}${fmt(Math.abs(mAct.balance))}`, color: SERIES[2].color, clase: mAct.balance < 0 ? 'text-danger' : 'text-ink' }] : []),
    ...(mAct.tasa_ahorro !== undefined ? [{ nombre: 'Tasa de ahorro', valor: mAct.tasa_ahorro === null ? '—' : `${String(Math.round(mAct.tasa_ahorro * 10) / 10).replace('.', ',')} %` }] : []),
  ]
  const pie = mAct?.variacion ? `Gastos vs mes anterior: ${textoVar(mAct.variacion.gastos_pct)}` : null
  const anuncio = mAct
    ? `${mAct.etiqueta_larga}: ingresos ${fmt(mAct.ingresos)}, gastos ${fmt(mAct.gastos)}, balance ${fmt(mAct.balance)}${mAct.tasa_ahorro != null ? `, tasa de ahorro ${mAct.tasa_ahorro} %` : ''}.${seleccion === mAct.mes ? ' Seleccionado.' : ''}`
    : ''
  const paso = meses.length > 14 ? 2 : 1

  return (
    <div>
      <div
        {...manejadores}
        ref={ref}
        tabIndex={0}
        role="group"
        aria-roledescription="gráfico interactivo"
        aria-label="Gráfico de ingresos, gastos y balance por mes. Con las flechas izquierda y derecha recorres los meses; Enter selecciona el mes."
        className="gr-lienzo relative md:max-w-[560px] md:mx-auto"
      >
        {mAct && <Lectura pct={(cx(activo) / W) * 100} titulo={mAct.etiqueta_larga} filas={filas} pie={pie} />}
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block" role="img" aria-label={resumen}>
          <defs>
            {SERIES.slice(0, 2).map((s) => (
              <linearGradient key={s.id} id={`${gid}-${s.id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor={s.color} stopOpacity="1" />
                <stop offset="1" stopColor={s.color} stopOpacity="0.62" />
              </linearGradient>
            ))}
            <linearGradient id={`${gid}-area`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--color-ink)" stopOpacity="0.14" />
              <stop offset="1" stopColor="var(--color-ink)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.izq} x2={W - M.der} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeOpacity={t === 0 ? 1 : 0.55} strokeWidth={t === 0 ? 1 : 0.6} />
              <text x={M.izq - 6} y={y(t) + 3} textAnchor="end" fontSize="9" fill="var(--color-ink-soft)" style={FUENTE}>{abreviarEje(t)}</text>
            </g>
          ))}
          {enfoque !== null && (
            <rect x={M.izq + g * enfoque + 1} y={M.arr} width={g - 2} height={ph} rx="6" fill="var(--color-ink)" opacity={activo !== null ? 0.07 : 0.045} />
          )}
          {meses.map((m, i) => {
            const atenuar = iSel >= 0 && i !== iSel && activo !== i ? 0.4 : 1
            return (
              <g key={m.mes} className="gr-atenuable" opacity={atenuar} data-mes={m.mes} data-seleccionado={i === iSel ? 'true' : undefined}>
                {visible('ingresos') && m.ingresos > 0 && (
                  <path className="gr-barra" style={{ '--i': i }} d={rutaBarra(cx(i) - ancho - 1, y(m.ingresos), ancho, y0)} fill={`url(#${gid}-ingresos)`} />
                )}
                {visible('gastos') && m.gastos > 0 && (
                  <path className="gr-barra" style={{ '--i': i }} d={rutaBarra(cx(i) + 1, y(m.gastos), ancho, y0)} fill={`url(#${gid}-gastos)`} />
                )}
                {i % paso === 0 && (
                  <text x={cx(i)} y={H - 6} textAnchor="middle" fontSize="10" fontWeight={i === iSel ? 700 : 400} fill={i === iSel ? 'var(--color-ink)' : 'var(--color-ink-soft)'} style={FUENTE}>{m.etiqueta}</text>
                )}
              </g>
            )
          })}
          {visible('balance') && meses.length > 1 && (
            <g className="gr-aparece">
              <path d={area} fill={`url(#${gid}-area)`} />
              <path className="gr-linea" pathLength="1" d={trazo} fill="none" stroke="var(--color-ink)" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
            </g>
          )}
          {visible('balance') && enfoque !== null && (
            <circle cx={cx(enfoque)} cy={y(meses[enfoque].balance)} r="3.6" fill="var(--color-paper-raised)" stroke="var(--color-ink)" strokeWidth="1.8" />
          )}
        </svg>
        <p className="sr-only" aria-live="polite" role="status">{anuncio}</p>
      </div>
      <ul className="flex flex-wrap gap-x-1 gap-y-1 text-[11px] mt-1" aria-label="Leyenda">
        {SERIES.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              aria-pressed={visible(s.id)}
              onClick={() => setOcultas((o) => (o.includes(s.id) ? o.filter((x) => x !== s.id) : [...o, s.id]))}
              className={`flex items-center gap-1.5 px-2 min-h-[44px] rounded-full ${visible(s.id) ? 'text-ink-soft' : 'text-ink-soft/60 line-through'}`}
            >
              <span className={s.id === 'balance' ? 'w-3 h-0.5' : 'w-2.5 h-2.5 rounded-sm'} style={{ background: s.color, opacity: visible(s.id) ? 1 : 0.3 }} aria-hidden="true" />
              {s.nombre}
            </button>
          </li>
        ))}
        {seleccion && onSeleccion && (
          <li className="ml-auto">
            <button type="button" onClick={() => onSeleccion(null)} className="px-3 min-h-[44px] text-accent font-semibold">Ver el periodo completo</button>
          </li>
        )}
      </ul>
      <table className="sr-only">
        <caption>Ingresos, gastos y balance por mes</caption>
        <thead><tr><th>Mes</th><th>Ingresos</th><th>Gastos</th><th>Balance</th></tr></thead>
        <tbody>
          {meses.map((m) => (
            <tr key={m.mes}><th scope="row">{m.etiqueta_larga}</th><td>{fmt(m.ingresos)} pesos</td><td>{fmt(m.gastos)} pesos</td><td>{fmt(m.balance)} pesos</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
