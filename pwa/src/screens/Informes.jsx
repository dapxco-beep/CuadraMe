import { lazy, Suspense } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { EmbebidoProvider } from '../lib/EmbebidoContext'
import { EsqueletoLista } from '../components/Esqueletos'

// Una sola puerta para «cómo voy»: antes eran cinco pantallas sueltas (Informe, Mi resumen, Cosas raras, Patrimonio y
// Cierre de mes), cada una con su flecha, su título y su selector de periodo. Cada pestaña muestra la pantalla de
// siempre, sin su encabezado propio (ver EmbebidoContext).
const Informe = lazy(() => import('./Informe'))
const Wrapped = lazy(() => import('./Wrapped'))
const Insights = lazy(() => import('./Insights'))
const Patrimonio = lazy(() => import('./Patrimonio'))
const CierreMes = lazy(() => import('./CierreMes'))

export const PESTANAS = [
  { id: 'gastos', texto: 'Gastos', Pantalla: Informe },
  { id: 'resumen', texto: 'Mi mes', Pantalla: Wrapped },
  { id: 'dias', texto: 'Días', Pantalla: Insights },
  { id: 'patrimonio', texto: 'Patrimonio', Pantalla: Patrimonio },
  { id: 'cierre', texto: 'Cierre', Pantalla: CierreMes },
]

export default function Informes() {
  const volver = useVolver('/')
  const [params, setParams] = useSearchParams()
  const activa = PESTANAS.find((p) => p.id === params.get('tab')) || PESTANAS[0]
  const { Pantalla } = activa

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button
          type="button"
          onClick={volver}
          className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Volver"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-semibold">Informes</h1>
      </header>

      <div role="tablist" aria-label="Informes" className="px-5 pb-1 flex gap-2 overflow-x-auto no-scrollbar" data-testid="pestanas-informes">
        {PESTANAS.map((p) => {
          const es = p.id === activa.id
          return (
            <button
              key={p.id}
              type="button"
              role="tab"
              aria-selected={es}
              onClick={() => setParams({ tab: p.id }, { replace: true })}
              className={`min-h-11 px-4 rounded-full text-sm font-semibold border whitespace-nowrap ${es ? 'bg-accent-soft text-accent border-accent' : 'bg-paper-raised text-ink border-line'}`}
            >
              {p.texto}
            </button>
          )
        })}
      </div>

      <div role="tabpanel" aria-label={activa.texto}>
        <EmbebidoProvider value>
          <Suspense fallback={<EsqueletoLista filas={4} className="mx-5 mt-6" etiqueta="Cargando el informe" />}>
            <Pantalla key={activa.id} />
          </Suspense>
        </EmbebidoProvider>
      </div>
    </div>
  )
}
