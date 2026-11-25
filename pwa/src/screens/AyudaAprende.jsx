import { lazy } from 'react'
import PantallaConPestanas from '../components/PantallaConPestanas'

const Ayuda = lazy(() => import('./Ayuda'))
const Aprende = lazy(() => import('./Aprende'))

export const PESTANAS_AYUDA = [
  { id: 'ayuda', texto: 'Ayuda', Pantalla: Ayuda },
  { id: 'aprende', texto: 'Aprende', Pantalla: Aprende },
]

export default function AyudaAprende() {
  return <PantallaConPestanas titulo="Ayuda" pestanas={PESTANAS_AYUDA} />
}
