import { Suspense } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { EmbebidoProvider } from '../lib/EmbebidoContext'
import { EsqueletoLista } from './Esqueletos'

// Una pantalla con título único, flecha de volver y pestañas. Cada pestaña muestra una pantalla de siempre, sin su
// encabezado propio (ver EmbebidoContext). La pestaña activa vive en la dirección: ?tab=<id>.
export default function PantallaConPestanas({ titulo, pestanas }) {
  const volver = useVolver('/')
  const [params, setParams] = useSearchParams()
  const activa = pestanas.find((p) => p.id === params.get('tab')) || pestanas[0]
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
        <h1 className="text-xl font-semibold">{titulo}</h1>
      </header>
      <div role="tablist" aria-label={titulo} className="px-5 pb-1 flex gap-2 overflow-x-auto no-scrollbar">
        {pestanas.map((p) => {
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
          <Suspense fallback={<EsqueletoLista filas={4} className="mx-5 mt-6" etiqueta="Cargando" />}>
            <Pantalla key={activa.id} />
          </Suspense>
        </EmbebidoProvider>
      </div>
    </div>
  )
}
