import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

// Enlaces a otras pantallas relacionadas. `enlaces`: [{ a: '/ruta', texto, apoyo? }]
export default function EnlacesRelacionados({ titulo = 'También te puede servir', enlaces }) {
  return (
    <section className="mx-5 mt-6" aria-label={titulo}>
      <h2 className="text-sm font-semibold mb-2">{titulo}</h2>
      <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
        {enlaces.map((e) => (
          <Link key={e.a} to={e.a} className="flex items-center gap-3 px-4 py-3 min-h-11">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{e.texto}</p>
              {e.apoyo && <p className="text-xs text-ink-soft mt-0.5">{e.apoyo}</p>}
            </div>
            <ChevronRight size={16} className="text-ink-soft shrink-0" aria-hidden="true" />
          </Link>
        ))}
      </div>
    </section>
  )
}
