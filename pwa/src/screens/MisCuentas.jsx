import { lazy } from 'react'
import PantallaConPestanas from '../components/PantallaConPestanas'

const Cuentas = lazy(() => import('./Cuentas'))
const Deudas = lazy(() => import('./Deudas'))

export const PESTANAS_CUENTAS = [
  { id: 'cuentas', texto: 'Cuentas', Pantalla: Cuentas },
  { id: 'deudas', texto: 'Deudas', Pantalla: Deudas },
]

export default function MisCuentas() {
  return <PantallaConPestanas titulo="Tus cuentas" pestanas={PESTANAS_CUENTAS} />
}
