import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Home, LayoutGrid, List, Moon, PieChart, Plus, Sun, SunMoon } from 'lucide-react'
import { Isotipo, Wordmark } from '../brand/Marca'
import { useTheme } from '../lib/ThemeContext'
import { ITEMS_MAS, HojaMas, estaEnMas } from './BottomNav'

// Navegación de pantallas anchas.
//  - modo "riel" (iPad vertical, 768-1023 px): 72 px, ícono + etiqueta corta.
//  - modo "lateral" (iPad horizontal y PC, ≥1024 px): 240 px con todos los destinos,
//    botón destacado "Agregar movimiento", tema y Perfil abajo.
// Los destinos salen de ITEMS_MAS (la misma lista de la hoja "Más" del teléfono).

const PRINCIPALES = [
  { to: '/', icon: Home, label: 'Inicio', corta: 'Inicio', atajo: 'G I' },
  { to: '/movimientos', icon: List, label: 'Movimientos', corta: 'Movim.', atajo: 'G M' },
  { to: '/presupuesto', icon: PieChart, label: 'Presupuesto', corta: 'Presup.', atajo: 'G P' },
]

const porRuta = Object.fromEntries(ITEMS_MAS.map((i) => [i.to, i]))
const RIEL_EXTRA = [
  { ...porRuta['/patrimonio'], corta: 'Patrim.' },
  { ...porRuta['/sincronizacion'], corta: 'Sincro.' },
]
const LATERAL_EXTRA = ITEMS_MAS.filter((i) => i.to !== '/perfil')
const PERFIL = porRuta['/perfil']

const SIGUIENTE_TEMA = { auto: 'calido', calido: 'dark', dark: 'auto' }
const TEMA_INFO = {
  auto: { icon: SunMoon, texto: 'Tema: automático' },
  calido: { icon: Sun, texto: 'Tema: claro' },
  dark: { icon: Moon, texto: 'Tema: oscuro' },
}

function Riel({ abrirMas, masActivo }) {
  const lista = [...PRINCIPALES, ...RIEL_EXTRA]
  return (
    <nav
      aria-label="Navegación principal"
      className="barra-lateral barra-riel flex flex-col items-center gap-1 py-4 bg-paper-raised border-r border-line"
    >
      <NavLink to="/agregar" aria-label="Agregar movimiento" title="Agregar movimiento (N)" className="mb-3 group">
        <span className="w-12 h-12 nav-ficha bg-accent text-paper-raised flex items-center justify-center shadow-lg shadow-accent/30 boton-hover">
          <Plus size={24} strokeWidth={2.5} />
        </span>
        <span className="block text-[11px] font-medium text-ink-soft text-center mt-1">Agregar</span>
      </NavLink>
      {lista.map(({ to, icon: Icon, label, corta }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          aria-label={label}
          title={label}
          className={({ isActive }) =>
            `nav-item w-[64px] flex flex-col items-center gap-0.5 py-1.5 rounded-xl ${isActive ? 'text-accent' : 'text-ink-soft'}`
          }
        >
          {({ isActive }) => (
            <>
              <span className={`w-11 h-7 flex items-center justify-center ${isActive ? 'bg-accent-soft card-marca-sm' : ''}`}>
                <Icon size={21} strokeWidth={isActive ? 2.4 : 2} />
              </span>
              <span className={`text-[11px] leading-tight ${isActive ? 'font-semibold' : 'font-medium'}`}>{corta}</span>
            </>
          )}
        </NavLink>
      ))}
      <button
        type="button"
        aria-haspopup="dialog"
        onClick={abrirMas}
        className={`nav-item w-[64px] flex flex-col items-center gap-0.5 py-1.5 rounded-xl ${masActivo ? 'text-accent' : 'text-ink-soft'}`}
      >
        <span className={`w-11 h-7 flex items-center justify-center ${masActivo ? 'bg-accent-soft card-marca-sm' : ''}`}>
          <LayoutGrid size={21} strokeWidth={masActivo ? 2.4 : 2} />
        </span>
        <span className="text-[11px] font-medium leading-tight">Más</span>
      </button>
    </nav>
  )
}

function Lateral() {
  const { theme, setTheme } = useTheme() || {}
  const info = TEMA_INFO[theme] || TEMA_INFO.auto
  const IconoTema = info.icon
  const enlace = ({ isActive }) =>
    `nav-item flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm ${
      isActive ? 'bg-accent-soft text-accent font-semibold' : 'text-ink-soft font-medium'
    }`

  return (
    <nav
      aria-label="Navegación principal"
      className="barra-lateral barra-completa flex flex-col gap-1 px-3 py-5 bg-paper-raised border-r border-line overflow-y-auto"
    >
      <div className="flex items-center gap-2.5 px-2 pb-4">
        <Isotipo size={30} />
        <Wordmark className="text-[20px]" />
      </div>

      <NavLink
        to="/agregar"
        title="Agregar movimiento (N)"
        className="boton-hover flex items-center justify-center gap-2 bg-accent text-paper-raised font-semibold text-sm rounded-2xl py-3 mb-3 shadow-lg shadow-accent/25"
      >
        <Plus size={18} strokeWidth={2.5} aria-hidden="true" />
        Agregar movimiento
        <kbd className="atajo-kbd ml-auto mr-1">N</kbd>
      </NavLink>

      <div className="flex flex-col gap-0.5">
        {PRINCIPALES.map(({ to, icon: Icon, label, atajo }) => (
          <NavLink key={to} to={to} end={to === '/'} className={enlace}>
            <Icon size={19} aria-hidden="true" />
            <span className="flex-1">{label}</span>
            <kbd className="atajo-kbd" aria-hidden="true">{atajo}</kbd>
          </NavLink>
        ))}
      </div>

      <p className="t-kicker text-ink-soft px-3 mt-4 mb-1">Más</p>
      <div className="flex flex-col gap-0.5">
        {LATERAL_EXTRA.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={enlace}>
            <Icon size={19} aria-hidden="true" />
            <span className="flex-1">{label}</span>
          </NavLink>
        ))}
      </div>

      <div className="mt-auto pt-4 flex flex-col gap-0.5 border-t border-line">
        <button
          type="button"
          onClick={() => setTheme?.(SIGUIENTE_TEMA[theme] || 'calido')}
          className="nav-item flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-ink-soft text-left"
          title="Cambiar tema (automático, claro, oscuro)"
        >
          <IconoTema size={19} aria-hidden="true" />
          {info.texto}
        </button>
        <NavLink to={PERFIL.to} className={enlace}>
          <PERFIL.icon size={19} aria-hidden="true" />
          {PERFIL.label}
        </NavLink>
      </div>
    </nav>
  )
}

export default function BarraLateral({ modo }) {
  const { pathname } = useLocation()
  const [mas, setMas] = useState(false)
  // Navegar (o usar atrás) cierra la hoja, igual que en la barra inferior
  useEffect(() => {
    setMas(false)
  }, [pathname])
  if (modo === 'lateral') return <Lateral />
  return (
    <>
      <Riel
        abrirMas={() => setMas(true)}
        masActivo={mas || (estaEnMas(pathname) && !['/patrimonio', '/sincronizacion'].some((r) => pathname.startsWith(r)))}
      />
      {mas && <HojaMas onCerrar={() => setMas(false)} pathname={pathname} />}
    </>
  )
}
