import { useMemo } from 'react'
import { pctTexto } from '../lib/informe'
import { abreviarEje } from '../lib/graficos'

const CORTOS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
const PLURAL = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábados', 'domingos']

/** Promedio de gasto por día de la semana (lunes a domingo). Cuenta los días SIN gasto como 0: el promedio es por día calendario. */
export function promediosPorDiaSemana(dias) {
  const suma = Array(7).fill(0)
  const cuenta = Array(7).fill(0)
  for (const d of dias || []) {
    const i = (new Date(`${d.dia}T12:00:00`).getDay() + 6) % 7
    suma[i] += d.gasto || 0
    cuenta[i] += 1
  }
  return suma.map((s, i) => ({ i, promedio: cuenta[i] ? Math.round(s / cuenta[i]) : 0, dias: cuenta[i] }))
}

/** Resume cuál es el día más caro y cuánto pesa frente al promedio de los demás días. null si no hay base. */
export function hallazgoDiaSemana(prom) {
  const con = prom.filter((p) => p.dias > 0)
  if (con.length < 5) return null
  const top = con.reduce((a, b) => (b.promedio > a.promedio ? b : a))
  const otros = con.filter((p) => p.i !== top.i)
  const base = otros.reduce((s, p) => s + p.promedio, 0) / otros.length
  if (!top.promedio || !base) return null
  return { ...top, nombre: PLURAL[top.i], vsResto: Math.round((top.promedio / base - 1) * 100) }
}

/** «¿Qué día gastas más?»: barras de lunes a domingo con el promedio de cada uno. Solo con 2 semanas o más de datos. */
export default function GastoPorDiaSemana({ dias, fmt, className = '' }) {
  const prom = useMemo(() => promediosPorDiaSemana(dias), [dias])
  const hall = useMemo(() => hallazgoDiaSemana(prom), [prom])
  if (!dias || dias.length < 14 || !hall) return null
  const max = Math.max(1, ...prom.map((p) => p.promedio))
  return (
    <section className={`card-marca bg-paper-raised border border-line p-3.5 ${className}`} aria-label="Gasto por día de la semana" data-testid="gasto-dia-semana">
      <h2 className="text-[15px] font-semibold">¿Qué día gastas más?</h2>
      <p className="text-xs text-ink-soft mt-0.5">
        Los <b className="text-ink">{hall.nombre}</b> gastas en promedio <b className="text-ink">{fmt(hall.promedio)}</b>
        {hall.vsResto > 5 ? <>, un {pctTexto(hall.vsResto).replace('+', '')} más que el resto de la semana.</> : <>.</>}
      </p>
      <div className="mt-3 grid grid-cols-7 gap-2 items-end h-28" role="img"
        aria-label={`Gasto promedio por día: ${prom.map((p) => `${PLURAL[p.i]} ${fmt(p.promedio)}`).join(', ')}.`}>
        {prom.map((p) => {
          const esTop = p.i === hall.i
          return (
            <div key={p.i} className="flex flex-col items-center justify-end h-full gap-1" aria-hidden="true">
              <span className={`text-[10px] ${esTop ? 'font-bold text-ink' : 'text-ink-soft'}`}>{p.promedio ? abreviarEje(p.promedio) : ''}</span>
              <span
                className="w-full rounded-t-lg"
                style={{ height: `${Math.max(4, (p.promedio / max) * 72)}px`, background: esTop ? 'var(--color-brand)' : 'color-mix(in srgb, var(--color-brand) 35%, var(--color-paper-raised))' }}
              />
            </div>
          )
        })}
      </div>
      <div className="grid grid-cols-7 gap-2 mt-1" aria-hidden="true">
        {CORTOS.map((d, i) => (
          <span key={d} className={`text-center text-[11px] font-semibold ${i === hall.i ? 'text-ink' : 'text-ink-soft'}`}>{d}</span>
        ))}
      </div>
    </section>
  )
}
