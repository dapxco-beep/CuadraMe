import { useId, useMemo, useState } from 'react'
import { abreviarEje, escalaBonita, fraseEvolucion, rutaBarra } from '../lib/graficos'
import { pctTexto } from '../lib/informe'
import { useEvolucionCategorias } from '../lib/useEvolucionCategorias'
import { useLectura } from '../lib/useLectura'
import Lectura from './Lectura'

// «Evolución por categoría»: cuánto gastaste mes a mes en una categoría (o en todas), con su promedio como línea
// punteada. Chips con las 5 más grandes, 6 o 12 meses, apilado por subcategoría cuando existen. Tocar/arrastrar
// o ←/→ muestran la lectura del mes (frente al mes anterior y frente a su promedio). Cifras del servidor.
const W = 320
const H = 190
const M = { izq: 42, der: 8, arr: 8, aba: 22 }
const FUENTE = { fontFamily: 'var(--font-sans)' }
const color = (i) => `var(--c-serie-${(i % 6) + 1})`

function textoVar(pct) {
  if (pct === null || pct === undefined) return 'sin base'
  if (pct === 0) return 'igual'
  return `${pct > 0 ? '↑' : '↓'} ${pctTexto(Math.abs(pct)).replace('+', '')}`
}

export default function EvolucionCategoria({ fmt, className = '' }) {
  const gid = useId()
  const [nMeses, setNMeses] = useState(6)
  const [cat, setCat] = useState(null)
  const base = useEvolucionCategorias(nMeses, null)
  const det = useEvolucionCategorias(nMeses, cat, cat !== null)
  const datos = base.datos
  const top = useMemo(() => (datos?.categorias || []).slice(0, 5), [datos])

  const serie = cat === null ? datos?.serie_total : datos?.categorias.find((c) => c.categoria === cat)
  const nombre = cat ?? 'tu gasto total'
  const subs = cat !== null && det.datos?.categoria === cat && det.datos.tiene_subcategorias ? det.datos.subcategorias : null

  const cols = useMemo(() => {
    if (!datos || !serie) return []
    return datos.meses.map((m, i) => ({
      ...m,
      valor: serie.valores[i],
      vsAnt: serie.vs_anterior_pct[i],
      vsProm: serie.vs_promedio_pct[i],
      segs: subs ? subs.map((s, k) => ({ nombre: s.subcategoria || 'Sin subcategoría', valor: s.valores[i], color: color(k) })).filter((s) => s.valor > 0) : [],
    }))
  }, [datos, serie, subs])

  const pw = W - M.izq - M.der
  const ph = H - M.arr - M.aba
  const g = pw / Math.max(cols.length, 1)
  const cx = (i) => M.izq + g * i + g / 2
  const { max, ticks } = useMemo(() => escalaBonita(0, Math.max(0, ...cols.map((c) => c.valor), serie?.promedio || 0)), [cols, serie])
  const y = (v) => M.arr + ph - (v / (max || 1)) * ph
  const y0 = y(0)
  const ancho = Math.max(8, Math.min(26, g * 0.6))
  const { ref, activo, manejadores } = useLectura({ n: cols.length, W, xDe: cx })

  if (base.error) return null
  if (base.cargando && !datos) {
    return <section className={`card-marca bg-paper-raised border border-line p-4 ${className}`} aria-busy="true"><h2 className="text-sm font-semibold">Evolución por categoría</h2><p className="text-xs text-ink-soft mt-2">Cargando…</p></section>
  }
  if (!datos?.hay_datos || !serie) return null

  const rs = serie.resumen
  const mesRes = rs ? datos.meses[rs.indice].etiqueta_larga.split(' de ')[0].toLowerCase() : ''
  const frase = fraseEvolucion(nombre, rs, mesRes)
  const c = activo !== null ? cols[activo] : null
  const filas = c && [
    { nombre: c.segs.length ? 'Total' : 'Gasto', valor: fmt(c.valor), color: c.segs.length ? 'transparent' : 'var(--color-brand)' },
    ...c.segs.map((s) => ({ nombre: s.nombre, valor: fmt(s.valor), color: s.color })),
    { nombre: 'Vs mes anterior', valor: textoVar(c.vsAnt) },
    { nombre: 'Vs su promedio', valor: textoVar(c.vsProm) },
  ]
  const resumen = `Gasto mensual de ${nombre}: ` + cols.map((m) => `${m.etiqueta_larga}${m.parcial ? ' (en curso)' : ''} ${fmt(m.valor)}`).join('; ') + `. Promedio ${fmt(serie.promedio)}.`
  const anuncio = c ? `${c.etiqueta_larga}: ${fmt(c.valor)}. Frente al mes anterior ${textoVar(c.vsAnt)}; frente a su promedio ${textoVar(c.vsProm)}.` : ''
  const paso = cols.length > 8 ? 2 : 1
  const leyenda = subs ? subs.map((s, k) => ({ nombre: s.subcategoria || 'Sin subcategoría', color: color(k) })) : []

  return (
    <section id="evolucion-categoria" className={`card-marca bg-paper-raised border border-line p-4 ${className}`} aria-label="Evolución por categoría">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-sm font-semibold">Evolución por categoría</h2>
        <div role="group" aria-label="Cantidad de meses" className="flex rounded-full bg-paper border border-line p-0.5 shrink-0">
          {[6, 12].map((n) => (
            <button key={n} type="button" aria-pressed={nMeses === n} onClick={() => setNMeses(n)}
              className={`px-3 min-h-[32px] relative after:content-[''] after:absolute after:-inset-y-1.5 after:inset-x-0 rounded-full text-xs font-semibold ${nMeses === n ? 'bg-accent text-white' : 'text-ink-soft'}`}>{n} meses</button>
          ))}
        </div>
      </div>

      <div role="group" aria-label="Categoría" className="flex gap-2 overflow-x-auto -mx-4 px-4 mt-3 pb-1">
        {[null, ...top.map((t) => t.categoria)].map((n) => (
          <button key={n ?? '__todas'} type="button" aria-pressed={cat === n} onClick={() => setCat(n)}
            className={`shrink-0 px-3 min-h-[44px] rounded-full text-xs font-semibold border ${cat === n ? 'bg-accent text-white border-accent' : 'bg-paper text-ink border-line'}`}>
            {n ?? 'Todas'}
          </button>
        ))}
      </div>

      <p className="text-sm mt-2" data-testid="frase-evolucion">{frase}</p>
      <p className="text-[11px] text-ink-soft">Promedio mensual: {fmt(serie.promedio)} (sin contar el mes en curso)</p>

      <div
        {...manejadores}
        ref={ref}
        tabIndex={0}
        role="group"
        aria-roledescription="gráfico interactivo"
        aria-label={`Gráfico del gasto mensual de ${nombre}. Con las flechas izquierda y derecha recorres los meses.`}
        className="gr-lienzo relative mt-2 md:max-w-[560px] md:mx-auto"
      >
        {c && <Lectura pct={(cx(activo) / W) * 100} titulo={`${c.etiqueta_larga}${c.parcial ? ' (en curso)' : ''}`} filas={filas} />}
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block" role="img" aria-label={resumen}>
          <defs>
            <linearGradient id={`${gid}-b`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--color-brand)" /><stop offset="1" stopColor="var(--color-brand)" stopOpacity="0.62" />
            </linearGradient>
          </defs>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.izq} x2={W - M.der} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeOpacity={t === 0 ? 1 : 0.55} strokeWidth={t === 0 ? 1 : 0.6} />
              <text x={M.izq - 6} y={y(t) + 3} textAnchor="end" fontSize="9" fill="var(--color-ink-soft)" style={FUENTE}>{abreviarEje(t)}</text>
            </g>
          ))}
          {activo !== null && <rect x={M.izq + g * activo + 1} y={M.arr} width={g - 2} height={ph} rx="6" fill="var(--color-ink)" opacity="0.07" />}
          {cols.map((m, i) => {
            let tope = y0
            return (
              <g key={m.mes} opacity={m.parcial ? 0.55 : 1}>
                {m.segs.length > 0
                  ? m.segs.map((s, k) => {
                      const alto = y0 - y(s.valor)
                      const ySup = tope - alto
                      const ult = k === m.segs.length - 1
                      const el = ult
                        ? <path key={s.nombre} className="gr-barra" style={{ '--i': i }} d={rutaBarra(cx(i) - ancho / 2, ySup, ancho, tope)} fill={s.color} />
                        : <rect key={s.nombre} className="gr-barra" style={{ '--i': i }} x={cx(i) - ancho / 2} y={ySup} width={ancho} height={alto} fill={s.color} />
                      tope = ySup
                      return el
                    })
                  : m.valor > 0 && <path className="gr-barra" style={{ '--i': i }} d={rutaBarra(cx(i) - ancho / 2, y(m.valor), ancho, y0)} fill={`url(#${gid}-b)`} />}
                {(cols.length - 1 - i) % paso === 0 && <text x={cx(i)} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--color-ink-soft)" style={FUENTE}>{m.etiqueta}</text>}
              </g>
            )
          })}
          {serie.promedio > 0 && (
            <g className="gr-aparece">
              <line x1={M.izq} x2={W - M.der} y1={y(serie.promedio)} y2={y(serie.promedio)} stroke="var(--color-ink)" strokeWidth="1.3" strokeDasharray="4 3" />
              <text x={W - M.der} y={y(serie.promedio) - 3} textAnchor="end" fontSize="9" fill="var(--color-ink)" style={FUENTE}>promedio</text>
            </g>
          )}
        </svg>
        <p className="sr-only" aria-live="polite" role="status">{anuncio}</p>
      </div>

      {leyenda.length > 0 && (
        <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-soft mt-1" aria-label="Subcategorías">
          {leyenda.map((l) => (
            <li key={l.nombre} className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: l.color }} aria-hidden="true" />{l.nombre}</li>
          ))}
        </ul>
      )}

      <table className="sr-only">
        <caption>Gasto mensual de {nombre}</caption>
        <thead><tr><th>Mes</th><th>Gasto</th><th>Vs mes anterior</th><th>Vs su promedio</th></tr></thead>
        <tbody>
          {cols.map((m) => (
            <tr key={m.mes}><th scope="row">{m.etiqueta_larga}</th><td>{fmt(m.valor)} pesos</td><td>{textoVar(m.vsAnt)}</td><td>{textoVar(m.vsProm)}</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
