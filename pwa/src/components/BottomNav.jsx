import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { LayoutGrid, Plus } from 'lucide-react'
import { HojaMas } from './MenuMas'
import Icono from './Icono'
import { PRINCIPALES, estaEnMas } from '../lib/navegacion'

// Los destinos viven en lib/navegacion.js (una sola fuente de verdad para esta barra,
// el riel y la barra lateral). Se re-exportan por compatibilidad.
export { ITEMS_MAS, estaEnMas } from '../lib/navegacion'
export { HojaMas }

// Barra inferior: Inicio · Movimientos · (+) · Presupuesto · Más.
// Por qué: lo que se abre a diario es ver/corregir movimientos y el presupuesto
// del mes; el resto vive en la hoja "Más" (agrupada y con buscador). Cinco destinos
// caben bien en 360 px y todos miden ≥ 48 px de alto.
const [INICIO, MOVIMIENTOS, PRESUPUESTO] = PRINCIPALES

export default function BottomNav() {
  const { pathname } = useLocation()
  const [abierto, setAbierto] = useState(false)
  const botonMas = useRef(null)
  const enMas = estaEnMas(pathname)
  const cerrar = useCallback(() => setAbierto(false), [])

  // Navegar (o usar atrás) cierra la hoja
  useEffect(() => {
    setAbierto(false)
  }, [pathname])

  const pestana = (p) => (
    <NavLink
      key={p.to}
      to={p.to}
      replace
      end={p.to === '/'}
      className={({ isActive }) =>
        `flex flex-col items-center justify-center gap-1 px-1 py-1 min-w-[64px] min-h-12 transition-colors ${isActive ? 'text-accent' : 'text-ink-soft'}`
      }
    >
      {({ isActive }) => <Pestana Icon={p.icon} label={p.label} activa={isActive} />}
    </NavLink>
  )

  return (
    <>
      <nav
        aria-label="Navegación principal"
        className="sticky bottom-0 inset-x-0 bg-paper/90 backdrop-blur-xl border-t border-line pb-[env(safe-area-inset-bottom)]"
      >
        <div className="flex items-center justify-between px-3 pt-2 pb-2">
          {pestana(INICIO)}
          {pestana(MOVIMIENTOS)}
          <NavLink to="/agregar?foco=monto" aria-label="Agregar movimiento" className="flex flex-col items-center justify-center -mt-6">
            {/* El "+" es la ficha de la marca: la pieza que agregas para que todo cuadre */}
            <span className="w-14 h-14 nav-ficha bg-accent text-paper-raised flex items-center justify-center shadow-lg shadow-accent/30 active:scale-95 transition-transform">
              <Plus size={24} strokeWidth={2.5} aria-hidden="true" />
            </span>
          </NavLink>
          {pestana(PRESUPUESTO)}

          <button
            ref={botonMas}
            type="button"
            aria-haspopup="dialog"
            aria-expanded={abierto}
            onClick={() => setAbierto(true)}
            className={`flex flex-col items-center justify-center gap-1 px-1 py-1 min-w-[64px] min-h-12 transition-colors ${
              enMas || abierto ? 'text-accent' : 'text-ink-soft'
            }`}
          >
            <Pestana Icon={LayoutGrid} label="Más" activa={enMas || abierto} />
          </button>
        </div>
      </nav>

      {abierto && <HojaMas onCerrar={cerrar} pathname={pathname} />}
    </>
  )
}

// Ícono con "ficha" de fondo cuando la pestaña está activa (misma esquina de la marca)
function Pestana({ Icon, label, activa }) {
  return (
    <>
      <span className={`w-12 h-7 flex items-center justify-center transition-colors ${activa ? 'bg-accent-soft card-marca-sm' : ''}`}>
        <Icono icono={Icon} tam="md" trazo={activa ? 2.4 : 2} />
      </span>
      <span className={`text-[11px] ${activa ? 'font-semibold' : 'font-medium'}`}>{label}</span>
    </>
  )
}
