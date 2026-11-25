import { lazy } from 'react'
import PantallaConPestanas from '../components/PantallaConPestanas'

// Todo lo que sirve para traer movimientos a CuadraMe, en un solo lugar: el extracto del banco, los avisos que llegan al
// correo y el registro automático de los pagos desde el celular (atajos).
const Sincronizacion = lazy(() => import('./Sincronizacion'))
const ConectarDispositivo = lazy(() => import('./ConectarDispositivo'))

const Extractos = () => <Sincronizacion />
const Correo = () => <Sincronizacion modo="correo" />

export const PESTANAS_TRAER = [
  { id: 'extractos', texto: 'Extractos', Pantalla: Extractos },
  { id: 'correo', texto: 'Correo', Pantalla: Correo },
  { id: 'automatico', texto: 'Automático', Pantalla: ConectarDispositivo },
]

export default function TraerMovimientos() {
  return <PantallaConPestanas titulo="Traer movimientos" pestanas={PESTANAS_TRAER} />
}
