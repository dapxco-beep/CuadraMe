import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { abreviarCOP } from '../lib/informe'

// «Día a día» de En qué gasto: lo que gastaste cada día y cuánta plata tenías disponible al cierre de cada
// uno, en el mismo periodo del informe. Dos vistas (Gasto | Disponible), un día elegido con detalle en texto
// (y flechas de 44 px para recorrerlos con el dedo) y los datos clave arriba de la gráfica.
const W = 320
const H = 150
const M = { izq: 6, der: 6, arr: 10, aba: 18 }
const SEMANAS_DESDE = 62 // con más días que esto las barras se agrupan por semana
const aria = { fontFamily: 'var(--font-sans)', fontStretch: 'normal', letterSpacing: 0 }

const fechaDe = (iso) => new Date(`${iso}T12:00:00`)
export const diaLargo = (iso) => fechaDe(iso).toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'short' })
const diaCorto = (iso) => fechaDe(iso).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })

// Agrupa los días en semanas (lunes a domingo) cuando el periodo es largo.
export function agruparSemanas(dias) {
  const out = []
  for (const d of dias) {
    const f = fechaDe(d.dia)
    const lunes = new Date(f.getFullYear(), f.getMonth(), f.getDate() - ((f.getDay() + 6) % 7))
    const k = `${lunes.getFullYear()}-${String(lunes.getMonth() + 1).padStart(2, '0')}-${String(lunes.getDate()).padStart(2, '0')}`
    const ult = out[out.length - 1]
    if (ult && ult.dia === k) {
      ult.gasto += d.gasto
      ult.ingreso += d.ingreso
      ult.disponible = d.disponible
    } else out.push({ dia: k, gasto: d.gasto, ingreso: d.ingreso, disponible: d.disponible, semana: true })
  }
  return out
}

export default function DiaADia({ desde, hasta, className = '' }) {
  const { fmt } = useBloqueo()
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [vista, setVista] = useState('gasto')
  const [sel, setSel] = useState(null)

  useEffect(() => {
    let activo = true
    setDatos(null)
    setError('')
    setSel(null)
    // El servidor acepta como máximo 400 días: si el periodo es más largo, se muestran los últimos 400.
    const limite = new Date(`${hasta}T12:00:00`)
    limite.setDate(limite.getDate() - 399)
    const desdeOk = desde && hasta && new Date(`${desde}T12:00:00`) < limite
      ? `${limite.getFullYear()}-${String(limite.getMonth() + 1).padStart(2, '0')}-${String(limite.getDate()).padStart(2, '0')}`
      : desde
    api.gastoDiario(desdeOk, hasta)
      .then((d) => activo && setDatos(d))
      .catch((e) => activo && setError(e.message || 'No pudimos cargar el día a día.'))
    return () => {
      activo = false
    }
  }, [desde, hasta])

  const dias = datos?.dias || []
  const barras = useMemo(() => (dias.length > SEMANAS_DESDE ? agruparSemanas(dias) : dias), [dias])
  const k = barras.length
  const idx = sel !== null && barras[sel] ? sel : k - 1 // por defecto, el último día
  const actual = barras[idx]

  if (error) return <p role="alert" className="mx-6 mt-4 text-xs text-danger">{error}</p>
  if (!datos) return <div className="mx-6 mt-4 h-40 rounded-2xl bg-paper-raised border border-line" role="status" aria-label="Cargando el día a día" />
  if (k === 0) return null

  const etiqueta = (d) => (d.semana ? `Semana del ${diaCorto(d.dia)}` : diaLargo(d.dia))
  const pw = W - M.izq - M.der
  const ph = H - M.arr - M.aba
  const paso = pw / k

  // ── Gasto por día ──
  const maxGasto = Math.max(1, ...barras.map((d) => d.gasto))
  const conGasto = dias.filter((d) => d.gasto > 0)
  const total = dias.reduce((s, d) => s + d.gasto, 0)
  const promedio = dias.length ? Math.round(total / dias.length) : 0
  const mayor = conGasto.length ? conGasto.reduce((a, b) => (b.gasto > a.gasto ? b : a)) : null

  // ── Disponible ──
  const vals = barras.map((d) => d.disponible)
  const lo = Math.min(...vals)
  const hi = Math.max(...vals)
  const margen = Math.max((hi - lo) * 0.12, 1)
  const yD = (v) => M.arr + ph - ((v - (lo - margen)) / (hi - lo + 2 * margen)) * ph
  const xD = (i) => M.izq + (k === 1 ? pw / 2 : (pw * i) / (k - 1))
  const linea = vals.map((v, i) => `${xD(i).toFixed(1)},${yD(v).toFixed(1)}`).join(' ')
  const area = `${xD(0).toFixed(1)},${(M.arr + ph).toFixed(1)} ${linea} ${xD(k - 1).toFixed(1)},${(M.arr + ph).toFixed(1)}`
  const primero = dias[0]?.disponible ?? 0
  const cambio = (datos.disponible_hoy ?? vals[k - 1]) - primero
  const bajo = dias.length ? dias.reduce((a, b) => (b.disponible < a.disponible ? b : a)) : null

  const mover = (d) => setSel(Math.min(k - 1, Math.max(0, idx + d)))

  return (
    <section className={`mx-6 mt-4 card-marca bg-paper-raised border border-line p-4 ${className}`} aria-label="Día a día" data-testid="dia-a-dia">
      <h2 className="text-[15px] font-semibold">Día a día</h2>
      <div className="flex gap-1.5 mt-2" role="group" aria-label="Qué ver día a día">
        {[['gasto', 'Lo que gastas'], ['disponible', 'Lo que te queda']].map(([id, nombre]) => (
          <button
            key={id}
            type="button"
            aria-pressed={vista === id}
            onClick={() => setVista(id)}
            className={`px-3.5 min-h-[44px] rounded-full text-xs font-semibold border ${
              vista === id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper text-ink-soft'
            }`}
          >
            {nombre}
          </button>
        ))}
      </div>

      {vista === 'gasto' ? (
        <p className="text-xs text-ink-soft mt-3" data-testid="resumen-gasto">
          Gastas en promedio <b className="text-ink">{fmt(promedio)}</b> al día
          {mayor ? <> · tu día más fuerte fue el <b className="text-ink">{diaCorto(mayor.dia)}</b> ({fmt(mayor.gasto)})</> : ''}
          {conGasto.length < dias.length ? ` · ${dias.length - conGasto.length} ${dias.length - conGasto.length === 1 ? 'día' : 'días'} sin gastar` : ''}.
        </p>
      ) : (
        <p className="text-xs text-ink-soft mt-3" data-testid="resumen-disponible">
          Hoy tienes <b className="text-ink">{fmt(datos.disponible_hoy ?? vals[k - 1])}</b> disponibles
          {Math.abs(cambio) >= 1 ? <> · {cambio > 0 ? 'subió' : 'bajó'} <b className={cambio > 0 ? 'text-cuadra' : 'text-danger'}>{fmt(Math.abs(cambio))}</b> desde el {diaCorto(dias[0].dia)}</> : ' · sin cambios en este periodo'}
          {bajo && bajo.disponible < primero ? <> · tu punto más bajo fue {fmt(bajo.disponible)} el {diaCorto(bajo.dia)}</> : ''}.
        </p>
      )}

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full mt-2"
        onClick={(e) => {
          // Tocar la gráfica elige el día más cercano (las flechas de abajo hacen lo mismo con botones grandes)
          const r = e.currentTarget.getBoundingClientRect()
          if (!r.width) return
          const x = ((e.clientX - r.left) / r.width) * W
          const i = vista === 'gasto' ? Math.floor((x - M.izq) / paso) : Math.round((x - M.izq) / (k > 1 ? pw / (k - 1) : 1))
          setSel(Math.min(k - 1, Math.max(0, i)))
        }}
        role="img" aria-label={vista === 'gasto' ? 'Gasto de cada día' : 'Plata disponible al cierre de cada día'} style={aria}>
        {vista === 'gasto' ? (
          <>
            <line x1={M.izq} x2={W - M.der} y1={M.arr + ph} y2={M.arr + ph} stroke="var(--c-line)" />
            {barras.map((d, i) => {
              const h = (d.gasto / maxGasto) * ph
              return (
                <rect
                  key={d.dia}
                  x={M.izq + paso * i + paso * 0.15}
                  y={M.arr + ph - Math.max(h, d.gasto > 0 ? 2 : 0)}
                  width={Math.max(2, paso * 0.7)}
                  height={Math.max(h, d.gasto > 0 ? 2 : 0)}
                  rx={1.5}
                  fill="var(--c-accent)"
                  opacity={i === idx ? 1 : 0.42}
                />
              )
            })}
            <text x={M.izq} y={H - 4} fontSize="9" fill="var(--c-ink-soft)">{diaCorto(barras[0].dia)}</text>
            <text x={W - M.der} y={H - 4} fontSize="9" textAnchor="end" fill="var(--c-ink-soft)">{diaCorto(barras[k - 1].dia)}</text>
            <text x={W - M.der} y={M.arr + 2} fontSize="9" textAnchor="end" fill="var(--c-ink-soft)">{abreviarCOP(maxGasto)}</text>
          </>
        ) : (
          <>
            <polygon points={area} fill="var(--c-accent)" opacity="0.12" />
            <polyline points={linea} fill="none" stroke="var(--c-accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            <circle cx={xD(idx)} cy={yD(vals[idx])} r="4" fill="var(--c-accent)" stroke="var(--c-paper-raised)" strokeWidth="2" />
            <text x={M.izq} y={H - 4} fontSize="9" fill="var(--c-ink-soft)">{diaCorto(barras[0].dia)}</text>
            <text x={W - M.der} y={H - 4} fontSize="9" textAnchor="end" fill="var(--c-ink-soft)">{diaCorto(barras[k - 1].dia)}</text>
            <text x={M.izq} y={M.arr + 2} fontSize="9" fill="var(--c-ink-soft)">{abreviarCOP(hi)}</text>
          </>
        )}
      </svg>

      <div className="flex items-center gap-1 mt-1">
        <button type="button" onClick={() => mover(-1)} disabled={idx === 0} aria-label="Día anterior" className="w-11 h-11 flex items-center justify-center rounded-full border border-line disabled:opacity-40">
          <ChevronLeft size={20} aria-hidden="true" />
        </button>
        <div className="flex-1 text-center min-w-0" aria-live="polite" data-testid="dia-elegido">
          <p className="text-xs font-semibold first-letter:uppercase truncate">{etiqueta(actual)}</p>
          <p className="text-[11px] text-ink-soft">
            {vista === 'gasto'
              ? `Gastaste ${fmt(actual.gasto)}${actual.ingreso > 0 ? ` · Entró ${fmt(actual.ingreso)}` : ''}`
              : `Tenías ${fmt(actual.disponible)}${actual.gasto > 0 ? ` · gastaste ${fmt(actual.gasto)}` : ''}`}
          </p>
        </div>
        <button type="button" onClick={() => mover(1)} disabled={idx === k - 1} aria-label="Día siguiente" className="w-11 h-11 flex items-center justify-center rounded-full border border-line disabled:opacity-40">
          <ChevronRight size={20} aria-hidden="true" />
        </button>
      </div>
    </section>
  )
}
