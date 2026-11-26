import { lazy, Suspense, useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { EmbebidoProvider } from '../lib/EmbebidoContext'
import { AccionesPantallaContext } from '../lib/AccionesPantallaContext'
import { EsqueletoLista } from '../components/Esqueletos'

// Cuentas y deudas en UNA pantalla: arriba tus cuentas y tarjetas; abajo lo que debes (préstamos y cuánto conviene
// pagar primero). Antes eran dos pestañas y la de deudas repetía las tarjetas que ya salen en las cuentas.
const Cuentas = lazy(() => import('./Cuentas'))
const Deudas = lazy(() => import('./Deudas'))

export default function MisCuentas() {
  const volver = useVolver('/')
  const [params] = useSearchParams()
  const [destinoAcciones, setDestinoAcciones] = useState(null) // línea del título: ahí van «ver/ocultar saldos» y «Nueva cuenta»
  // Los enlaces viejos a «Deudas» (/deudas, ?tab=deudas) bajan hasta su sección
  useEffect(() => {
    if (params.get('tab') !== 'deudas') return undefined
    const t = setTimeout(() => document.getElementById('deudas')?.scrollIntoView?.({ block: 'start' }), 600)
    return () => clearTimeout(t)
  }, [params])

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter pantalla-ancha">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button
          type="button"
          onClick={volver}
          className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Volver"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-semibold">Tus cuentas</h1>
        <div ref={setDestinoAcciones} data-testid="acciones-pantalla" className="ml-auto shrink-0 flex items-center gap-2 [&>div:empty]:hidden" />
      </header>
      <EmbebidoProvider value>
        <AccionesPantallaContext.Provider value={destinoAcciones}>
          <Suspense fallback={<EsqueletoLista filas={4} className="mx-5 mt-6" etiqueta="Cargando" />}>
            <Cuentas />
            <section id="deudas" aria-label="Préstamos y deudas" className="mt-6 scroll-mt-4">
              <Deudas enCuentas />
            </section>
          </Suspense>
        </AccionesPantallaContext.Provider>
      </EmbebidoProvider>
    </div>
  )
}
