import { lazy, Suspense } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useVolver } from '../lib/useVolver'
import { EmbebidoProvider } from '../lib/EmbebidoContext'
import { EsqueletoLista } from '../components/Esqueletos'

// Dos revisiones que se parecen —lo que pasaste entre tus cuentas (no cuenta como gasto) y lo que parece repetido—
// ahora van en UNA sola pantalla, una debajo de la otra: casi siempre una de las dos está vacía y con pestañas había
// que abrir cada una para saberlo.
const RevisarTraslados = lazy(() => import('./RevisarTraslados'))
const BuscarDuplicados = lazy(() => import('./BuscarDuplicados'))

export default function RevisarMovimientos() {
  const volver = useVolver('/movimientos')
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
        <h1 className="text-xl font-semibold">Revisar movimientos</h1>
      </header>
      <EmbebidoProvider value>
        <Suspense fallback={<EsqueletoLista filas={4} className="mx-5 mt-6" etiqueta="Cargando" />}>
          <section aria-labelledby="rev-traslados" className="mt-3">
            <h2 id="rev-traslados" className="t-kicker px-6 mb-1">Plata que pasaste entre tus cuentas</h2>
            <RevisarTraslados />
          </section>
          <section aria-labelledby="rev-repetidos" className="mt-6">
            <h2 id="rev-repetidos" className="t-kicker px-6 mb-1">Movimientos que parecen repetidos</h2>
            <BuscarDuplicados />
          </section>
        </Suspense>
      </EmbebidoProvider>
    </div>
  )
}
