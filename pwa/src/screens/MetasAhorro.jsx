import { lazy } from 'react'
import PantallaConPestanas from '../components/PantallaConPestanas'

const Metas = lazy(() => import('./Metas'))
const Inversiones = lazy(() => import('./Inversiones'))

export const PESTANAS_AHORRO = [
  { id: 'metas', texto: 'Metas', Pantalla: Metas },
  { id: 'inversiones', texto: 'Inversiones', Pantalla: Inversiones },
]

export default function MetasAhorro() {
  return <PantallaConPestanas titulo="Metas y ahorro" pestanas={PESTANAS_AHORRO} />
}
