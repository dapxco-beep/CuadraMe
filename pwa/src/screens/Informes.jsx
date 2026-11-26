import { lazy, Suspense } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { EmbebidoProvider } from '../lib/EmbebidoContext'
import { EsqueletoLista } from '../components/Esqueletos'
import { useModoMenu } from '../lib/modoSimple'
import { PeriodoInformeProvider } from '../lib/periodoInforme'
import BarraPeriodo from '../components/informe/BarraPeriodo'

const AVANZADAS = ['patrimonio', 'impuestos']

// Una sola puerta para «cómo voy»: antes eran cinco pantallas sueltas (Informe, Mi resumen, Cosas raras, Patrimonio y
// Cierre de mes), cada una con su flecha, su título y su selector de periodo. Cada pestaña muestra la pantalla de
// siempre, sin su encabezado propio (ver EmbebidoContext).
const Panorama = lazy(() => import('./Panorama'))
const Informe = lazy(() => import('./Informe'))
const Wrapped = lazy(() => import('./Wrapped'))
const Patrimonio = lazy(() => import('./Patrimonio'))
const CierreMes = lazy(() => import('./CierreMes'))
const Impuestos = lazy(() => import('./Impuestos'))

export const PESTANAS = [
  { id: 'panorama', texto: 'Resumen', Pantalla: Panorama },
  { id: 'gastos', texto: 'Gastos', Pantalla: Informe },
  { id: 'resumen', texto: 'Mi mes', Pantalla: Wrapped },
  { id: 'patrimonio', texto: 'Patrimonio', Pantalla: Patrimonio },
  { id: 'cierre', texto: 'Cierre', Pantalla: CierreMes },
  { id: 'impuestos', texto: 'Impuestos', Pantalla: Impuestos },
]

function Cuerpo() {
  const volver = useVolver('/')
  const [params, setParams] = useSearchParams()
  const activa = PESTANAS.find((p) => p.id === params.get('tab')) || PESTANAS[0]
  const { Pantalla } = activa
  const { perfil } = useModoMenu()
  // Cambiar de pestaña conserva el periodo (y lo demás de la dirección).
  const irA = (id) =>
    setParams(
      (prev) => {
        const n = new URLSearchParams(prev)
        n.set('tab', id)
        return n
      },
      { replace: true }
    )
  const visibles = PESTANAS.filter((p) => perfil !== 'esencial' || !AVANZADAS.includes(p.id) || p.id === activa.id)

  return (
    <div className={`flex-1 overflow-y-auto pb-6 screen-enter${['gastos', 'panorama'].includes(activa.id) ? ' pantalla-ancha' : ''}`}>
      <header className="px-5 pantalla-top pb-1 flex items-center gap-3">
        <button
          type="button"
          onClick={volver}
          className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Volver"
        >
          <ArrowLeft size={20} />
        </button>
        <div className="min-w-0">
          <h1 className="text-xl font-semibold leading-tight">Informes</h1>
          <p className="text-xs text-ink-soft leading-snug">Analiza tu comportamiento financiero y descubre oportunidades de mejora.</p>
        </div>
      </header>

      <div role="tablist" aria-label="Informes" className="pl-5 pr-9 pb-1 flex gap-2 overflow-x-auto no-scrollbar borde-fade-der" data-testid="pestanas-informes">
        {visibles.map((p) => {
          const es = p.id === activa.id
          return (
            <button
              key={p.id}
              type="button"
              role="tab"
              aria-selected={es}
              ref={es ? (el) => el?.scrollIntoView?.({ inline: 'center', block: 'nearest' }) : undefined}
              onClick={() => irA(p.id)}
              className={`min-h-11 px-4 rounded-full text-sm font-semibold border whitespace-nowrap ${es ? 'bg-accent-soft text-accent border-accent' : 'bg-paper-raised text-ink border-line'}`}
            >
              {p.texto}
            </button>
          )
        })}
      </div>

      <BarraPeriodo className="px-5 mt-2" />

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

export default function Informes() {
  return (
    <PeriodoInformeProvider>
      <Cuerpo />
    </PeriodoInformeProvider>
  )
}
