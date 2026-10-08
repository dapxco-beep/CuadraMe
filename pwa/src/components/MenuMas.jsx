import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Clock, Search, SearchX, X } from 'lucide-react'
import Hoja from './Hoja'
import Icono from './Icono'
import { useAuth } from '../lib/AuthContext'
import { buscarDestinos, DESTINO_ADMIN, esAdminVisible, GRUPOS, leerRecientes, rutaCoincide } from '../lib/navegacion'

// Menú «Más»: los destinos agrupados por tema, con buscador arriba y «Recientes».
// Se usa en la barra inferior (teléfono) y en el riel (iPad vertical).

function Destino({ item, pathname, onIr, compacto = false }) {
  const { to, icon, label } = item
  const activo = rutaCoincide(pathname, to)
  return (
    <Link
      to={to}
      onClick={(e) => onIr(e, to)}
      aria-current={activo ? 'page' : undefined}
      className={`h-full flex items-center gap-3 border card-marca-sm text-left ${
        compacto ? 'px-3 py-2.5 min-h-[48px]' : 'px-3 py-3 min-h-[52px]'
      } ${activo ? 'bg-accent-soft border-accent text-accent' : 'bg-paper-raised border-line text-ink'}`}
    >
      <Icono icono={icon} tam="md" className={activo ? '' : 'text-accent'} />
      <span className="text-[13px] font-medium leading-tight">{label}</span>
    </Link>
  )
}

export function HojaMas({ onCerrar, pathname }) {
  const navigate = useNavigate()
  const admin = esAdminVisible(useAuth()?.usuario?.email)
  const [consulta, setConsulta] = useState('')
  const recientes = useMemo(() => leerRecientes(), [])
  const resultados = useMemo(() => buscarDestinos(consulta), [consulta])
  const buscando = consulta.trim().length > 0

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

  function alTeclearBuscador(e) {
    if (e.key === 'Escape' && consulta) {
      // Primer Escape: borra la búsqueda; el segundo cierra la hoja
      e.preventDefault()
      e.stopPropagation()
      setConsulta('')
    } else if (e.key === 'Enter' && resultados[0]) {
      irA(e, resultados[0].to)
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
              <Icono icono={X} tam="md" />
            </button>
          </div>

          <div className="relative mb-4">
            <Icono icono={Search} tam="sm" className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-soft pointer-events-none" />
            <input
              type="search"
              value={consulta}
              onChange={(e) => setConsulta(e.target.value)}
              onKeyDown={alTeclearBuscador}
              placeholder="Buscar: deudas, metas, reglas…"
              aria-label="Buscar en el menú"
              autoComplete="off"
              enterKeyHint="go"
              className="w-full h-11 rounded-full bg-paper-raised border border-line pl-10 pr-4 text-sm placeholder:text-ink-soft outline-none focus:border-accent"
            />
          </div>

          {buscando ? (
            resultados.length > 0 ? (
              <ul className="grid grid-cols-1 gap-2" aria-label="Resultados de la búsqueda">
                {resultados.map((item) => (
                  <li key={item.to}>
                    <Destino item={item} pathname={pathname} onIr={irA} compacto />
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-center py-8" role="status">
                <Icono icono={SearchX} tam="lg" className="mx-auto text-ink-soft" />
                <p className="text-sm font-medium mt-2">No encontré «{consulta.trim()}»</p>
                <p className="text-xs text-ink-soft mt-1">Prueba con otra palabra, por ejemplo «cuentas» o «ahorro».</p>
              </div>
            )
          ) : (
            <>
              {recientes.length > 0 && (
                <section aria-labelledby="mas-recientes" className="mb-4">
                  <h3 id="mas-recientes" className="t-kicker text-ink-soft mb-2 flex items-center gap-1.5">
                    <Icono icono={Clock} tam="sm" /> Recientes
                  </h3>
                  <ul className="grid grid-cols-2 gap-2">
                    {recientes.map((item) => (
                      <li key={item.to}>
                        <Destino item={item} pathname={pathname} onIr={irA} compacto />
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {GRUPOS.map((g) => (
                <section key={g.id} aria-labelledby={`mas-${g.id}`} className="mb-4 last:mb-0">
                  <h3 id={`mas-${g.id}`} className="t-kicker text-ink-soft mb-2">
                    {g.titulo}
                  </h3>
                  <ul className="grid grid-cols-2 gap-2">
                    {g.items.map((item) => (
                      <li key={item.to}>
                        <Destino item={item} pathname={pathname} onIr={irA} />
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
              {admin && (
                <section aria-labelledby="mas-admin" className="mt-4">
                  <h3 id="mas-admin" className="t-kicker text-ink-soft mb-2">
                    Administración
                  </h3>
                  <ul className="grid grid-cols-2 gap-2">
                    <li>
                      <Destino item={DESTINO_ADMIN} pathname={pathname} onIr={irA} />
                    </li>
                  </ul>
                </section>
              )}
            </>
          )}
        </>
      )}
    </Hoja>
  )
}
