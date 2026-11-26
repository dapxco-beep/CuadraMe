import { Link, useSearchParams } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Info, Lightbulb } from 'lucide-react'
import { Panel } from './comun'

// Hallazgos: reglas deterministas sobre las cifras del periodo (informe_resumen.hallazgos). Cada uno trae su texto con
// las cifras, el periodo y a dónde ir a verlo. Si no hay base para afirmar algo, no aparece (no se rellena).
const TONOS = {
  bueno: { Icono: CheckCircle2, clase: 'text-cuadra', etiqueta: 'Buena noticia' },
  atento: { Icono: AlertTriangle, clase: 'text-danger', etiqueta: 'Ojo' },
  neutro: { Icono: Info, clase: 'text-ink-soft', etiqueta: 'Dato' },
}

/** Conserva el periodo elegido al saltar a otra pestaña de Informes. */
export function destinoHallazgo(enlace, params) {
  const [ruta, consulta = ''] = enlace.split('?')
  const n = new URLSearchParams(consulta)
  if (ruta === '/informes') for (const k of ['p', 'desde', 'hasta']) if (params.get(k)) n.set(k, params.get(k))
  const q = n.toString()
  return q ? `${ruta}?${q}` : ruta
}

export default function Hallazgos({ hallazgos, etiqueta }) {
  const [params] = useSearchParams()
  if (!hallazgos?.length) return null
  return (
    <Panel
      icono={Lightbulb}
      titulo="Lo que dicen tus números"
      pregunta={`Lo más importante · ${etiqueta}`}
      info="Cada frase sale de una regla fija sobre tus movimientos reales (comparar con el periodo anterior, ver qué categoría pesa más, revisar tus presupuestos). No son consejos genéricos: si no hay datos para afirmar algo, no se muestra."
    >
      <ul className="divide-y divide-line lg:divide-y-0 lg:grid lg:grid-cols-2 lg:gap-x-10">
        {hallazgos.map((h) => {
          const t = TONOS[h.tono] || TONOS.neutro
          return (
            <li key={h.id} className="py-3 first:pt-0 last:pb-0 flex gap-3 lg:border-t lg:border-line lg:pt-3 lg:pb-1 lg:first:pt-3 lg:last:pb-1">
              <t.Icono size={20} className={`${t.clase} shrink-0 mt-0.5`} aria-hidden="true" />
              <div className="min-w-0">
                <p className="text-sm font-semibold leading-snug">
                  <span className="sr-only">{t.etiqueta}: </span>
                  {h.titulo}
                </p>
                <p className="text-xs text-ink-soft mt-0.5 leading-relaxed">{h.texto}</p>
                <Link to={destinoHallazgo(h.enlace, params)} className="inline-flex items-center min-h-11 text-xs font-semibold text-accent">
                  Ver el detalle
                </Link>
              </div>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
