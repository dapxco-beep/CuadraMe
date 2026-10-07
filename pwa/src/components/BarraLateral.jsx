import { useEffect, useMemo, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { ChevronDown, Clock, LayoutGrid, Moon, Plus, Search, Sun, SunMoon } from 'lucide-react'
import { Isotipo, Wordmark } from '../brand/Marca'
import { useTheme } from '../lib/ThemeContext'
import { HojaMas } from './MenuMas'
import Icono from './Icono'
import {
  GRUPOS, ITEMS_MAS, PRINCIPALES, buscarDestinos, estaEnMas, guardarGruposCerrados, leerGruposCerrados,
  leerRecientes, rutaCoincide,
} from '../lib/navegacion'

// Navegación de pantallas anchas.
//  - modo "riel" (iPad vertical, 768-1023 px): 72 px, ícono + etiqueta corta; «Más» abre el
//    mismo menú agrupado con buscador que el teléfono.
//  - modo "lateral" (iPad horizontal y PC, ≥1024 px): 240 px con buscador, recientes y los
//    destinos en grupos plegables (se recuerda cuáles estaban cerrados).
// Todos los destinos salen de lib/navegacion.js.

const porRuta = Object.fromEntries(ITEMS_MAS.map((i) => [i.to, i]))
const RIEL_EXTRA = [porRuta['/patrimonio'], porRuta['/sincronizacion']]
const RUTAS_RIEL_EXTRA = RIEL_EXTRA.map((i) => i.to)

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
          <Plus size={24} strokeWidth={2.5} aria-hidden="true" />
        </span>
        <span className="block text-[11px] font-medium text-ink-soft text-center mt-1">Agregar</span>
      </NavLink>
      {lista.map(({ to, icon, label, corta }) => (
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
                <Icono icono={icon} tam="md" trazo={isActive ? 2.4 : 2} />
              </span>
              <span className={`text-[11px] leading-tight ${isActive ? 'font-semibold' : 'font-medium'}`}>{corta || label}</span>
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
          <Icono icono={LayoutGrid} tam="md" trazo={masActivo ? 2.4 : 2} />
        </span>
        <span className="text-[11px] font-medium leading-tight">Más</span>
      </button>
    </nav>
  )
}

const claseEnlace = ({ isActive }) =>
  `nav-item flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm ${
    isActive ? 'bg-accent-soft text-accent font-semibold' : 'text-ink-soft font-medium'
  }`

function EnlaceLateral({ item, end }) {
  return (
    <NavLink to={item.to} end={end} className={claseEnlace}>
      <Icono icono={item.icon} tam="md" />
      <span className="flex-1">{item.label}</span>
      {item.atajo && (
        <kbd className="atajo-kbd" aria-hidden="true">
          {item.atajo}
        </kbd>
      )}
    </NavLink>
  )
}

function Lateral() {
  const { theme, setTheme } = useTheme() || {}
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const info = TEMA_INFO[theme] || TEMA_INFO.auto
  const [consulta, setConsulta] = useState('')
  const [cerrados, setCerrados] = useState(leerGruposCerrados)
  const recientes = useMemo(() => leerRecientes(), [pathname]) // eslint-disable-line react-hooks/exhaustive-deps
  const resultados = useMemo(() => buscarDestinos(consulta), [consulta])
  const buscando = consulta.trim().length > 0

  // Si vas a una pantalla de un grupo plegado, el grupo se abre para que veas dónde estás
  useEffect(() => {
    const grupo = GRUPOS.find((g) => g.items.some((i) => rutaCoincide(pathname, i.to)))
    if (grupo) {
      setCerrados((c) => {
        if (!c.includes(grupo.id)) return c
        const nuevo = c.filter((id) => id !== grupo.id)
        guardarGruposCerrados(nuevo)
        return nuevo
      })
    }
  }, [pathname])

  function alternar(id) {
    setCerrados((c) => {
      const nuevo = c.includes(id) ? c.filter((x) => x !== id) : [...c, id]
      guardarGruposCerrados(nuevo)
      return nuevo
    })
  }

  function alTeclearBuscador(e) {
    if (e.key === 'Escape' && consulta) {
      e.preventDefault()
      setConsulta('')
    } else if (e.key === 'Enter' && resultados[0]) {
      navigate(resultados[0].to)
      setConsulta('')
      e.currentTarget.blur()
    }
  }

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
        {PRINCIPALES.map((p) => (
          <EnlaceLateral key={p.to} item={p} end={p.to === '/'} />
        ))}
      </div>

      <div className="relative mt-3 mb-1">
        <Icono icono={Search} tam="sm" className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft pointer-events-none" />
        <input
          type="search"
          data-atajo-menu
          value={consulta}
          onChange={(e) => setConsulta(e.target.value)}
          onKeyDown={alTeclearBuscador}
          placeholder="Buscar en el menú"
          aria-label="Buscar en el menú"
          autoComplete="off"
          className="w-full h-10 rounded-xl bg-paper border border-line pl-9 pr-8 text-sm placeholder:text-ink-soft outline-none focus:border-accent"
        />
        <kbd className="atajo-kbd absolute right-2 top-1/2 -translate-y-1/2" aria-hidden="true">/</kbd>
      </div>

      {buscando ? (
        <div className="flex flex-col gap-0.5 mt-1" role="list" aria-label="Resultados de la búsqueda">
          {resultados.length === 0 && (
            <p className="text-xs text-ink-soft px-3 py-2" role="status">
              No encontré «{consulta.trim()}».
            </p>
          )}
          {resultados.map((item) => (
            <div role="listitem" key={item.to}>
              <EnlaceLateral item={{ ...item, atajo: undefined }} />
            </div>
          ))}
        </div>
      ) : (
        <>
          {recientes.length > 0 && (
            <section aria-labelledby="lat-recientes" className="mt-2">
              <p id="lat-recientes" className="t-kicker text-ink-soft px-3 mt-1 mb-1 flex items-center gap-1.5">
                <Icono icono={Clock} tam="sm" /> Recientes
              </p>
              <div className="flex flex-col gap-0.5">
                {recientes.map((item) => (
                  <EnlaceLateral key={item.to} item={{ ...item, atajo: undefined }} />
                ))}
              </div>
            </section>
          )}
          {GRUPOS.map((g) => {
            const abierto = !cerrados.includes(g.id)
            return (
              <section key={g.id} className="mt-2">
                <button
                  type="button"
                  id={`lat-btn-${g.id}`}
                  aria-expanded={abierto}
                  aria-controls={`lat-${g.id}`}
                  onClick={() => alternar(g.id)}
                  className="nav-item w-full flex items-center gap-2 px-3 py-1.5 rounded-lg t-kicker text-ink-soft text-left"
                >
                  <span className="flex-1">{g.titulo}</span>
                  <Icono icono={ChevronDown} tam="sm" className={`transition-transform ${abierto ? '' : '-rotate-90'}`} />
                </button>
                <div id={`lat-${g.id}`} role="group" aria-labelledby={`lat-btn-${g.id}`} hidden={!abierto} className="flex flex-col gap-0.5 mt-0.5">
                  {g.items.map((item) => (
                    <EnlaceLateral key={item.to} item={item} />
                  ))}
                </div>
              </section>
            )
          })}
        </>
      )}

      <div className="mt-auto pt-4 flex flex-col gap-0.5 border-t border-line">
        <button
          type="button"
          onClick={() => setTheme?.(SIGUIENTE_TEMA[theme] || 'calido')}
          className="nav-item flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-ink-soft text-left"
          title="Cambiar tema (automático, claro, oscuro)"
        >
          <Icono icono={info.icon} tam="md" />
          {info.texto}
        </button>
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
  // El atajo «/» en el riel (no tiene buscador a la vista) abre el menú «Más»
  useEffect(() => {
    if (modo !== 'riel') return undefined
    const abrir = () => setMas(true)
    window.addEventListener('cuadrame:abrir-menu', abrir)
    return () => window.removeEventListener('cuadrame:abrir-menu', abrir)
  }, [modo])
  if (modo === 'lateral') return <Lateral />
  return (
    <>
      <Riel abrirMas={() => setMas(true)} masActivo={mas || (estaEnMas(pathname) && !RUTAS_RIEL_EXTRA.some((r) => pathname.startsWith(r)))} />
      {mas && <HojaMas onCerrar={() => setMas(false)} pathname={pathname} />}
    </>
  )
}
