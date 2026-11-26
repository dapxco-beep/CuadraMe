import { lazy, Suspense, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import PantallaConPestanas from '../components/PantallaConPestanas'
import { EsqueletoLista } from '../components/Esqueletos'

// Ordenar en qué categoría cae cada gasto: «Categorías» (con sus reglas automáticas debajo) y «Por categorizar».
// Las reglas eran una pestaña con una lista muy corta: ahora son una sección de Categorías.
const Categorias = lazy(() => import('./Categorias'))
const ReglasCategoria = lazy(() => import('./ReglasCategoria'))
const PorCategorizar = lazy(() => import('./PorCategorizar'))

function CategoriasYReglas() {
  const [params] = useSearchParams()
  // Los enlaces viejos a «Reglas» (/reglas-categoria, ?tab=reglas) bajan hasta su sección
  useEffect(() => {
    if (params.get('tab') !== 'reglas') return undefined
    const t = setTimeout(() => document.getElementById('reglas')?.scrollIntoView?.({ block: 'start' }), 600)
    return () => clearTimeout(t)
  }, [params])
  return (
    <Suspense fallback={<EsqueletoLista filas={3} className="mx-5 mt-6" etiqueta="Cargando" />}>
      <Categorias />
      <section id="reglas" aria-labelledby="titulo-reglas" className="mt-8 scroll-mt-4">
        <h2 id="titulo-reglas" className="t-kicker px-6">Reglas automáticas</h2>
        <ReglasCategoria />
      </section>
    </Suspense>
  )
}

export const PESTANAS_CATEGORIAS = [
  { id: 'categorias', texto: 'Categorías', Pantalla: CategoriasYReglas },
  { id: 'pendientes', texto: 'Por categorizar', Pantalla: PorCategorizar },
]

export default function OrdenarCategorias() {
  return <PantallaConPestanas titulo="Categorías" pestanas={PESTANAS_CATEGORIAS} />
}
