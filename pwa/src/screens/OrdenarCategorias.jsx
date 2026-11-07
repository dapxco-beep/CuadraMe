import { lazy } from 'react'
import PantallaConPestanas from '../components/PantallaConPestanas'

// Antes eran tres pantallas sueltas con el mismo trabajo: ordenar en qué categoría cae cada gasto.
const Categorias = lazy(() => import('./Categorias'))
const ReglasCategoria = lazy(() => import('./ReglasCategoria'))
const PorCategorizar = lazy(() => import('./PorCategorizar'))

export const PESTANAS_CATEGORIAS = [
  { id: 'categorias', texto: 'Categorías', Pantalla: Categorias },
  { id: 'reglas', texto: 'Reglas', Pantalla: ReglasCategoria },
  { id: 'pendientes', texto: 'Por categorizar', Pantalla: PorCategorizar },
]

export default function OrdenarCategorias() {
  return <PantallaConPestanas titulo="Categorías" pestanas={PESTANAS_CATEGORIAS} />
}
