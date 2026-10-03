import { useEffect, useState } from 'react'
import { ChevronDown, HeartPulse, Lightbulb } from 'lucide-react'
import { api } from '../lib/api'

export function colorPuntaje(p) {
  if (p >= 70) return 'var(--c-accent)'
  if (p >= 40) return 'var(--c-accent-2)'
  return 'var(--c-danger)'
}

// Anillo SVG: el trazo se anima con una transición CSS de stroke-dashoffset.
// Se monta en 0 y un instante después pasa al valor real, por eso "se llena".
export function AnilloPuntaje({ score, size = 96 }) {
  const [lleno, setLleno] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setLleno(true), 60)
    return () => clearTimeout(t)
  }, [])
  const r = 40
  const circ = 2 * Math.PI * r
  const offset = circ * (1 - (lleno ? score : 0) / 100)
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--c-line)" strokeWidth="9" />
        <circle
          cx="50" cy="50" r={r} fill="none" strokeWidth="9" strokeLinecap="round"
          stroke={colorPuntaje(score)}
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 1s cubic-bezier(0.22, 1, 0.36, 1)' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-extrabold leading-none">{score}</span>
        <span className="text-[10px] text-ink-soft">de 100</span>
      </div>
    </div>
  )
}

export default function TarjetaSalud() {
  const [datos, setDatos] = useState(null)
  const [abierto, setAbierto] = useState(false)

  useEffect(() => {
    let activo = true
    try {
      api
        .saludFinanciera()
        // solo se acepta una respuesta con la forma esperada
        .then((d) => activo && typeof d?.score === 'number' && Array.isArray(d.componentes) && setDatos({ ...d, consejos: d.consejos || [] }))
        .catch(() => {})
    } catch {
      /* sin endpoint disponible: la tarjeta simplemente no aparece */
    }
    return () => {
      activo = false
    }
  }, [])

  if (!datos) return null

  return (
    <section
      aria-label="Salud financiera"
      className="mx-6 mt-3 rounded-2xl bg-paper-raised border border-line p-4 stagger-item"
      style={{ '--stagger-i': 4 }}
    >
      <div className="flex items-center gap-4">
        <AnilloPuntaje score={datos.score} />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-ink-soft flex items-center gap-1">
            <HeartPulse size={13} /> Salud financiera
          </p>
          <p className="text-lg font-bold">{datos.nivel}</p>
          {datos.consejos[0] && <p className="text-xs text-ink-soft mt-1">{datos.consejos[0]}</p>}
        </div>
      </div>

      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className="w-full flex items-center justify-center gap-1 text-xs text-accent font-semibold mt-3"
      >
        {abierto ? 'Ocultar desglose' : 'Ver desglose'}
        <ChevronDown size={14} className={`transition-transform ${abierto ? 'rotate-180' : ''}`} />
      </button>

      {abierto && (
        <div className="mt-3 pt-3 border-t border-line space-y-3 pop-in">
          {datos.componentes.map((c) => (
            <div key={c.clave}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-medium">{c.nombre}</span>
                <span className="text-ink-soft">{c.disponible ? `${c.puntaje}/100` : 'Sin datos aún'}</span>
              </div>
              <div className="h-1.5 rounded-full bg-line overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${c.disponible ? c.puntaje : 0}%`,
                    background: colorPuntaje(c.puntaje ?? 0),
                    transition: 'width 0.8s cubic-bezier(0.22, 1, 0.36, 1)',
                  }}
                />
              </div>
            </div>
          ))}
          {datos.consejos.length > 0 && (
            <div className="rounded-xl bg-accent-soft p-3 space-y-2">
              {datos.consejos.map((t) => (
                <p key={t} className="text-xs text-ink flex gap-2">
                  <Lightbulb size={14} className="text-accent shrink-0 mt-0.5" />
                  <span>{t}</span>
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
