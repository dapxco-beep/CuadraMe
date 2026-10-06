import BottomNav from './BottomNav'
import BarraLateral from './BarraLateral'
import { useModoPantalla } from '../lib/useAncho'
import { useAtajosTeclado } from '../lib/atajos'

// Estructura de la app autenticada:
//  - <768 px (teléfono): columna de 480 px con barra inferior, igual que siempre.
//  - ≥768 px (iPad vertical): riel lateral de 72 px y contenido centrado (~720 px).
//  - ≥1024 px (iPad horizontal / PC): barra lateral de 240 px y contenido más ancho.
// Los anchos viven en index.css (.app-shell / .app-contenido); aquí solo se decide
// qué navegación se monta, para que no existan dos navegaciones a la vez.
export default function ShellApp({ children }) {
  const modo = useModoPantalla()
  useAtajosTeclado()
  return (
    <div className="app-shell" data-modo={modo}>
      {modo !== 'movil' && <BarraLateral modo={modo} />}
      <div className="app-contenido">
        {children}
        {modo === 'movil' && <BottomNav />}
      </div>
    </div>
  )
}
