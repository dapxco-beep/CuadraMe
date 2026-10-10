import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Lightbulb, X } from 'lucide-react'
import { api } from '../lib/api'
import { AVISO_EDUCATIVO } from '../lib/avisoEducativo'
import Icono from './Icono'
import Cuadri from '../brand/Cuadri'
import { useMostrarCuadri } from '../lib/cuadri'
import { Boton } from './ui'

const LLAVE = 'cuadrame:consejos-descartados'
const MAX_VISIBLES = 3
const MAX_GUARDADOS = 200

// Descartados: se guardan en este dispositivo (solo ids de texto, sin datos del usuario). Cada consejo
// trae un `id` estable que incluye el periodo o la situación, así que si hay algo nuevo (otro mes, otra
// tarjeta) vuelve a salir; lo ya descartado no se repite.
function leerDescartados() {
  try {
    const v = JSON.parse(localStorage.getItem(LLAVE) || '[]')
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

function guardarDescartados(ids) {
  try {
    localStorage.setItem(LLAVE, JSON.stringify(ids.slice(-MAX_GUARDADOS)))
  } catch {
    /* sin almacenamiento: el consejo reaparece al recargar, no pasa nada */
  }
}

/**
 * «Consejo para ti» en Inicio: hasta 3 consejos personalizados (reglas del servidor, sin IA externa),
 * en un carrusel descartable. Si falla la carga o no hay consejos, no pinta nada.
 * Orientación educativa: no recomienda productos ni inversiones.
 */
export default function ConsejoParaTi({ max = MAX_VISIBLES }) {
  const [lista, setLista] = useState([])
  const [aviso, setAviso] = useState(AVISO_EDUCATIVO)
  const [descartados, setDescartados] = useState(leerDescartados)
  const [indice, setIndice] = useState(0)
  const toque = useRef(null)
  const [conCuadri] = useMostrarCuadri()

  useEffect(() => {
    let activo = true
    Promise.resolve()
      .then(() => api.consejos?.())
      .then((r) => {
        if (!activo || !r) return
        const consejos = Array.isArray(r) ? r : r.consejos
        if (Array.isArray(consejos)) setLista(consejos)
        if (r.aviso) setAviso(r.aviso)
      })
      .catch(() => {})
    return () => {
      activo = false
    }
  }, [])

  const visibles = lista.filter((c) => !descartados.includes(c.id)).slice(0, max)
  if (!visibles.length) return null

  const i = Math.min(indice, visibles.length - 1)
  const c = visibles[i]

  function descartar() {
    const nuevos = [...descartados, c.id]
    setDescartados(nuevos)
    guardarDescartados(nuevos)
    setIndice((x) => Math.max(0, Math.min(x, visibles.length - 2)))
  }

  const ir = (n) => setIndice((n + visibles.length) % visibles.length)

  return (
    <section
      className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line"
      aria-roledescription="carrusel"
      aria-label="Consejo para ti"
      data-testid="consejo-para-ti"
      onTouchStart={(e) => {
        toque.current = e.touches[0]?.clientX ?? null
      }}
      onTouchEnd={(e) => {
        const x0 = toque.current
        toque.current = null
        const dx = x0 == null ? 0 : (e.changedTouches[0]?.clientX ?? x0) - x0
        if (visibles.length > 1 && Math.abs(dx) > 50) ir(i + (dx < 0 ? 1 : -1))
      }}
    >
      <div className="flex items-center gap-2 px-4 pt-3">
        {conCuadri ? (
          // Cuadri «habla» en los consejos educativos y se preocupa (suave) en los avisos de prioridad 1–2.
          // Nunca juzga el gasto: solo acompaña. El texto del consejo es el que comunica.
          <Cuadri pose={c.prioridad <= 2 ? 'preocupado' : 'hablando'} size={40} className="-ml-1" />
        ) : (
          <span className="w-7 h-7 rounded-lg bg-accent-soft text-accent flex items-center justify-center shrink-0">
            <Icono icono={Lightbulb} tam="sm" />
          </span>
        )}
        <h2 className="t-kicker flex-1">Consejo para ti</h2>
        <button
          type="button"
          onClick={descartar}
          aria-label={`Descartar consejo: ${c.titulo}`}
          className="shrink-0 w-11 h-11 -mr-2 flex items-center justify-center text-ink-soft"
        >
          <Icono icono={X} tam="sm" />
        </button>
      </div>

      <div className="px-4 pb-3" aria-live="polite" data-testid="consejo" key={c.id}>
        <div className="flex items-start gap-2">
          <h3 className="flex-1 t-cuerpo font-semibold">{c.titulo}</h3>
          {c.cifra && (
            <span className="shrink-0 rounded-full bg-accent-soft text-accent px-2.5 py-0.5 text-xs font-semibold" data-testid="consejo-cifra">
              {c.cifra}
            </span>
          )}
        </div>
        <p className="t-cuerpo mt-1">{c.texto}</p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3">
          <Boton to={c.accion.ruta} tam="sm" variante="suave">
            {c.accion.texto}
          </Boton>
          {c.aprende && (
            <Link to={`/aprende?l=${c.aprende}`} className="text-sm text-accent font-medium min-h-11 inline-flex items-center">
              Entender por qué
            </Link>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 px-4 pb-3">
        <p className="t-apoyo flex-1">{aviso}</p>
        {visibles.length > 1 && (
          <div className="flex items-center gap-1 shrink-0">
            <button type="button" onClick={() => ir(i - 1)} aria-label="Consejo anterior" className="w-11 h-11 flex items-center justify-center text-ink-soft">
              <Icono icono={ChevronLeft} tam="sm" />
            </button>
            <span className="t-apoyo" aria-label={`Consejo ${i + 1} de ${visibles.length}`}>
              {i + 1}/{visibles.length}
            </span>
            <button type="button" onClick={() => ir(i + 1)} aria-label="Consejo siguiente" className="w-11 h-11 flex items-center justify-center text-ink-soft">
              <Icono icono={ChevronRight} tam="sm" />
            </button>
          </div>
        )}
      </div>
    </section>
  )
}
