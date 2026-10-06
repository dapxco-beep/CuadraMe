import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink, Link, useLocation, useNavigate } from 'react-router-dom'
import Hoja from './Hoja'
import {
  Bot, CalendarCheck, CreditCard, FileCheck, Receipt, Gift, Home, Landmark, LayoutGrid, List, Mail, PieChart, PiggyBank,
  Plus, RefreshCw, Repeat, Sparkles, Sprout, Tag, User, Wallet, X,
} from 'lucide-react'

// Barra inferior: Inicio · Movimientos · (+) · Presupuesto · Más.
// Por qué: lo que se abre a diario es ver/corregir movimientos y el presupuesto
// del mes; Patrimonio, Metas, Deudas y Perfil se consultan de vez en cuando, así
// que viven en la hoja "Más" (un toque) y Patrimonio además tiene acceso directo
// en Inicio. Cinco destinos caben bien en 360 px y todos miden ≥ 48 px de alto.
const tabs = [
  { to: '/', icon: Home, label: 'Inicio' },
  { to: '/movimientos', icon: List, label: 'Movimientos' },
  { to: '/agregar', icon: Plus, label: '', primary: true },
  { to: '/presupuesto', icon: PieChart, label: 'Presupuesto' },
]

export const ITEMS_MAS = [
  { to: '/asistente', icon: Bot, label: 'CuadraMe AI' },
  { to: '/patrimonio', icon: Landmark, label: 'Patrimonio' },
  { to: '/metas', icon: PiggyBank, label: 'Metas' },
  { to: '/deudas', icon: CreditCard, label: 'Deudas' },
  { to: '/recurrentes', icon: Repeat, label: 'Recurrentes' },
  { to: '/cuentas', icon: Wallet, label: 'Cuentas' },
  { to: '/insights', icon: Sparkles, label: 'Insights' },
  { to: '/resumen', icon: Gift, label: 'Resumen del mes' },
  { to: '/cierre-mes', icon: CalendarCheck, label: 'Cierre de mes' },
  { to: '/impuestos', icon: Receipt, label: 'Impuestos' },
  { to: '/sincronizacion', icon: RefreshCw, label: 'Sincronización' },
  { to: '/correos', icon: Mail, label: 'Correos' },
  { to: '/conciliacion', icon: FileCheck, label: 'Conciliar extracto' },
  { to: '/categorias', icon: Tag, label: 'Categorías' },
  { to: '/ahorcado', icon: Sprout, label: 'Árbol financiero' },
  { to: '/perfil', icon: User, label: 'Perfil y ajustes' },
]

// "Más" se ve activo cuando estás en cualquiera de sus pantallas (o parientes).
const RUTAS_MAS = [...ITEMS_MAS.map((i) => i.to), '/compartir', '/importar', '/reglas-categoria', '/conectar-dispositivo', '/legal']

export function estaEnMas(pathname) {
  return RUTAS_MAS.some((r) => pathname === r || pathname.startsWith(`${r}/`))
}

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

  return (
    <>
      <nav
        aria-label="Navegación principal"
        className="sticky bottom-0 inset-x-0 bg-paper/90 backdrop-blur-xl border-t border-line pb-[env(safe-area-inset-bottom)]"
      >
        <div className="flex items-center justify-between px-3 pt-2 pb-2">
          {tabs.map(({ to, icon: Icon, label, primary }) =>
            primary ? (
              <NavLink
                key={to}
                to={to}
                aria-label="Agregar movimiento"
                className="flex flex-col items-center justify-center -mt-6"
              >
                {/* El "+" es la ficha de la marca: la pieza que agregas para que todo cuadre */}
                <span className="w-14 h-14 nav-ficha bg-accent text-paper-raised flex items-center justify-center shadow-lg shadow-accent/30 active:scale-95 transition-transform">
                  <Icon size={26} strokeWidth={2.5} />
                </span>
              </NavLink>
            ) : (
              <NavLink
                key={to}
                to={to}
                replace
                end={to === '/'}
                className={({ isActive }) =>
                  `flex flex-col items-center gap-1 px-1 py-1 min-w-[64px] transition-colors duration-200 ${
                    isActive ? 'text-accent' : 'text-ink-soft'
                  }`
                }
              >
                {({ isActive }) => <Pestana Icon={Icon} label={label} activa={isActive} />}
              </NavLink>
            )
          )}

          <button
            ref={botonMas}
            type="button"
            aria-haspopup="dialog"
            aria-expanded={abierto}
            onClick={() => setAbierto(true)}
            className={`flex flex-col items-center gap-1 px-1 py-1 min-w-[64px] transition-colors duration-200 ${
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
      <span
        className={`w-12 h-7 flex items-center justify-center transition-colors duration-200 ${
          activa ? 'bg-accent-soft card-marca-sm' : ''
        }`}
      >
        <Icon size={21} strokeWidth={activa ? 2.4 : 2} />
      </span>
      <span className={`text-[11px] ${activa ? 'font-semibold' : 'font-medium'}`}>{label}</span>
    </>
  )
}

export function HojaMas({ onCerrar, pathname }) {
  const navigate = useNavigate()

  // Ir a una pantalla desde la hoja: primero se cierra la hoja con "atrás" (así se retira su
  // entrada de historial) y luego se navega con push normal. Si se navegara con la hoja
  // abierta, "atrás" desde la pantalla nueva caería en una entrada fantasma de la anterior.
  function irA(e, to) {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button > 0) return // nueva pestaña: comportamiento normal
    e.preventDefault()
    if (window.history.state?.__hoja) {
      const alRetroceder = () => {
        window.removeEventListener('popstate', alRetroceder)
        navigate(to)
      }
      window.addEventListener('popstate', alRetroceder)
      window.history.back()
    } else {
      navigate(to)
    }
  }

  return (
    <Hoja
      onCerrar={onCerrar}
      ariaLabel="Más opciones"
      clasePanel="px-5 pt-3 pb-[max(1.5rem,env(safe-area-inset-bottom))]"
    >
      {({ cerrar }) => (
        <>
          <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-line" aria-hidden="true" />
          <div className="flex items-center justify-between mb-3">
            <h2 className="t-title text-lg">Más</h2>
            <button
              type="button"
              onClick={cerrar}
              aria-label="Cerrar"
              className="w-11 h-11 -mr-2 rounded-full flex items-center justify-center text-ink-soft"
            >
              <X size={20} />
            </button>
          </div>
          <ul className="grid grid-cols-3 gap-2.5">
            {ITEMS_MAS.map(({ to, icon: Icon, label }) => {
              const activo = pathname === to || pathname.startsWith(`${to}/`)
              return (
                <li key={to}>
                  <Link
                    to={to}
                    onClick={(e) => irA(e, to)}
                    className={`h-full min-h-[84px] flex flex-col items-center justify-center gap-2 px-1.5 py-3 text-center border card-marca-sm ${
                      activo ? 'bg-accent-soft border-accent text-accent' : 'bg-paper-raised border-line text-ink'
                    }`}
                  >
                    <Icon size={22} strokeWidth={2} className={activo ? '' : 'text-accent'} />
                    <span className="text-[12px] font-medium leading-tight">{label}</span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </Hoja>
  )
}
