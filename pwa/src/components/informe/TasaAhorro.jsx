import { useEffect, useMemo, useState } from 'react'
import { PiggyBank } from 'lucide-react'
import { curvaSuave, escalaBonita } from '../../lib/graficos'
import { useLectura } from '../../lib/useLectura'
import Lectura from '../Lectura'
import { Panel, conSigno, pctSimple } from './comun'

// Tasa de ahorro mes a mes = (ingresos − gastos) ÷ ingresos. Responde: «¿estoy ahorrando más o menos que antes?».
// La serie y el promedio los calcula el servidor (informe.serie_mensual + informe_resumen.resumen_tasa). Un mes sin
// ingresos NO tiene tasa (hueco, no 0 %). El eje se limita a ±100 % para que un mes extremo no aplaste a los demás;
// el valor real siempre se ve en la lectura.
const W = 320
const H = 180
const M = { izq: 44, der: 12, arr: 14, aba: 24 }
const FUENTE = { fontFamily: 'var(--font-sans)' }
const TOPE = 100
const AYUDA =
  'Tasa de ahorro = flujo neto ÷ ingresos del mes. Con 20 % ahorraste 20 de cada 100 pesos que te entraron; si es negativa, ' +
  'gastaste más de lo que ganaste ese mes. El promedio pesa cada mes según sus ingresos (suma de lo ahorrado ÷ suma de ' +
  'ingresos). Los meses sin ingresos no tienen tasa y se dejan en blanco. Toca un mes para ver ese periodo completo.'

const recortar = (v) => Math.max(-TOPE, Math.min(TOPE, v))

export default function TasaAhorro({ meses, resumen, fmt, onVerMes }) {
  const [sel, setSel] = useState(null)
  useEffect(() => setSel(null), [meses])
  const n = meses.length
  const pw = W - M.izq - M.der
  const ph = H - M.arr - M.aba
  const g = pw / Math.max(n, 1)
  const x = (i) => M.izq + g * i + g / 2
  const con = meses.filter((m) => m.tasa_ahorro !== null)

  const { min, max, ticks } = useMemo(() => {
    const v = con.map((m) => recortar(m.tasa_ahorro))
    return escalaBonita(Math.min(0, ...v), Math.max(10, ...v))
  }, [con])
  const y = (v) => M.arr + ph - ((recortar(v) - min) / (max - min || 1)) * ph
  const y0 = M.arr + ph - ((0 - min) / (max - min || 1)) * ph

  // Tramos continuos: un mes sin tasa corta la línea.
  const tramos = useMemo(() => {
    const out = []
    let cur = []
    meses.forEach((m, i) => {
      if (m.tasa_ahorro === null) {
        if (cur.length) out.push(cur)
        cur = []
      } else cur.push([x(i), y(m.tasa_ahorro)])
    })
    if (cur.length) out.push(cur)
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meses, min, max])

  const elegir = (i) => setSel((s) => (s === i ? null : i))
  const { ref, activo, manejadores } = useLectura({ n, W, xDe: x, onElegir: elegir })
  const mAct = activo !== null ? meses[activo] : null
  const enfoque = activo ?? sel
  const elegido = sel !== null ? meses[sel] : null
  const filas = (m) => [
    { nombre: 'Tasa de ahorro', valor: pctSimple(m.tasa_ahorro), clase: m.tasa_ahorro !== null && m.tasa_ahorro < 0 ? 'text-danger' : 'text-ink' },
    { nombre: 'Ingresos', valor: fmt(m.ingresos), color: 'var(--color-cuadra)' },
    { nombre: 'Gastos', valor: fmt(m.gastos), color: 'var(--color-brand)' },
  ]
  const paso = n > 14 ? 2 : 1
  const aria = 'Tasa de ahorro por mes: ' + meses.map((m) => `${m.etiqueta_larga}, ${m.tasa_ahorro === null ? 'sin ingresos' : pctSimple(m.tasa_ahorro)}`).join('; ')

  return (
    <Panel icono={PiggyBank} titulo="Tasa de ahorro" pregunta="¿Estás ahorrando más o menos que en los meses anteriores?" info={AYUDA}>
      {con.length === 0 ? (
        <p className="text-sm text-ink-soft">Para calcular la tasa de ahorro necesitas ingresos registrados. Cuando los haya, verás aquí cómo evoluciona mes a mes.</p>
      ) : (
        <>
          {resumen?.promedio !== null && resumen?.promedio !== undefined && (
            <p className="text-sm">
              <span className="text-2xl font-bold t-cifra t-display">{pctSimple(resumen.promedio)}</span>
              <span className="text-xs text-ink-soft"> de tus ingresos se ahorró en promedio ({resumen.meses_con_tasa} {resumen.meses_con_tasa === 1 ? 'mes' : 'meses'} con ingresos)</span>
            </p>
          )}
          <div
            {...manejadores}
            ref={ref}
            tabIndex={0}
            role="group"
            aria-roledescription="gráfico interactivo"
            aria-label="Gráfico de la tasa de ahorro por mes. Con las flechas izquierda y derecha recorres los meses; Enter selecciona uno."
            className="gr-lienzo relative mt-2 md:max-w-[640px] md:mx-auto"
          >
            {mAct && <Lectura pct={(x(activo) / W) * 100} titulo={mAct.etiqueta_larga} filas={filas(mAct)} />}
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block" role="img" aria-label={aria}>
              {ticks.map((t) => (
                <g key={t}>
                  <line x1={M.izq} x2={W - M.der} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeOpacity={t === 0 ? 1 : 0.55} strokeWidth={t === 0 ? 1.2 : 0.6} />
                  <text x={M.izq - 6} y={y(t) + 3} textAnchor="end" fontSize="11" fill="var(--color-ink-soft)" style={FUENTE}>{t} %</text>
                </g>
              ))}
              {enfoque !== null && <rect x={M.izq + g * enfoque + 0.5} y={M.arr} width={Math.max(g - 1, 2)} height={ph} rx="4" fill="var(--color-ink)" opacity="0.06" />}
              {tramos.map((t, k) =>
                t.length > 1 ? (
                  <path key={k} className="gr-linea" pathLength="1" d={curvaSuave(t)} fill="none" stroke="var(--color-cuadra)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
                ) : null
              )}
              {meses.map((m, i) =>
                m.tasa_ahorro === null ? (
                  <g key={m.mes}>
                    {/* mes sin ingresos: una equis en la línea del 0 % (hueco explícito, no un cero) */}
                    <path d={`M${x(i) - 3},${y0 - 3}l6,6m0,-6l-6,6`} stroke="var(--color-ink-soft)" strokeWidth="1.3" fill="none" />
                  </g>
                ) : (
                  <g key={m.mes}>
                    {m.tasa_ahorro < 0 ? (
                      <rect x={x(i) - 3.5} y={y(m.tasa_ahorro) - 3.5} width="7" height="7" rx="1" fill="var(--color-danger)" stroke="var(--color-paper-raised)" strokeWidth="1" />
                    ) : (
                      <circle cx={x(i)} cy={y(m.tasa_ahorro)} r="3.5" fill="var(--color-cuadra)" stroke="var(--color-paper-raised)" strokeWidth="1" />
                    )}
                    {(i === n - 1 || i === sel) && (
                      <text x={x(i)} y={y(m.tasa_ahorro) - 8} textAnchor={i === n - 1 && n > 1 ? 'end' : 'middle'} fontSize="11" fontWeight="700" fill="var(--color-ink)" style={FUENTE}>{pctSimple(m.tasa_ahorro)}</text>
                    )}
                  </g>
                )
              )}
              {meses.map((m, i) =>
                i % paso === 0 ? (
                  <text key={m.mes} x={x(i)} y={H - 7} textAnchor="middle" fontSize="11" fontWeight={i === sel ? 700 : 400} fill={i === sel ? 'var(--color-ink)' : 'var(--color-ink-soft)'} style={FUENTE}>{m.etiqueta}</text>
                ) : null
              )}
            </svg>
            <p className="sr-only" aria-live="polite" role="status">
              {mAct ? `${mAct.etiqueta_larga}: tasa de ahorro ${mAct.tasa_ahorro === null ? 'no disponible, sin ingresos' : pctSimple(mAct.tasa_ahorro)}.` : ''}
            </p>
          </div>
          <p className="text-[11px] text-ink-soft mt-1">● ahorraste  ■ gastaste más de lo que ganaste  ✕ mes sin ingresos</p>

          {elegido ? (
            <div className="mt-2 rounded-xl bg-paper border border-line p-3 text-xs">
              <p className="font-semibold first-letter:uppercase">{elegido.etiqueta_larga}</p>
              <p className="mt-0.5 text-ink-soft">
                {elegido.tasa_ahorro === null
                  ? 'No hubo ingresos, así que no hay tasa de ahorro.'
                  : `Ahorraste el ${pctSimple(elegido.tasa_ahorro)} de tus ingresos: entró ${fmt(elegido.ingresos)}, salió ${fmt(elegido.gastos)} (flujo neto ${conSigno(elegido.balance, fmt)}).`}
              </p>
              <button type="button" onClick={() => onVerMes(elegido.mes)} className="inline-flex items-center min-h-11 font-semibold text-accent">
                Ver {elegido.etiqueta_larga} en todo el informe
              </button>
            </div>
          ) : (
            resumen?.mejor && (
              <p className="mt-2 text-xs text-ink-soft leading-relaxed">
                Tu mejor mes: {resumen.mejor.etiqueta_larga} ({pctSimple(resumen.mejor.tasa_ahorro)}).
                {resumen.peor && resumen.peor.mes !== resumen.mejor.mes && ` El más bajo: ${resumen.peor.etiqueta_larga} (${pctSimple(resumen.peor.tasa_ahorro)}).`}
              </p>
            )
          )}
        </>
      )}
    </Panel>
  )
}
