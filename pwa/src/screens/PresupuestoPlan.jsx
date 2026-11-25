import { lazy } from 'react'
import PantallaConPestanas from '../components/PantallaConPestanas'

const Presupuesto = lazy(() => import('./Presupuesto'))
const Recurrentes = lazy(() => import('./Recurrentes'))

export const PESTANAS_PLAN = [
  { id: 'presupuesto', texto: 'Presupuesto', Pantalla: Presupuesto },
  { id: 'fijos', texto: 'Pagos fijos', Pantalla: Recurrentes },
]

export default function PresupuestoPlan() {
  return <PantallaConPestanas titulo="Presupuesto" pestanas={PESTANAS_PLAN} raiz />
}
