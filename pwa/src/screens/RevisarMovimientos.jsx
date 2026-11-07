import { lazy } from 'react'
import PantallaConPestanas from '../components/PantallaConPestanas'

// Dos revisiones que se parecen: lo que pasaste entre tus cuentas (no cuenta como gasto) y lo que parece repetido.
const RevisarTraslados = lazy(() => import('./RevisarTraslados'))
const BuscarDuplicados = lazy(() => import('./BuscarDuplicados'))

export const PESTANAS_REVISAR = [
  { id: 'traslados', texto: 'Entre mis cuentas', Pantalla: RevisarTraslados },
  { id: 'repetidos', texto: 'Repetidos', Pantalla: BuscarDuplicados },
]

export default function RevisarMovimientos() {
  return <PantallaConPestanas titulo="Revisar movimientos" pestanas={PESTANAS_REVISAR} />
}
