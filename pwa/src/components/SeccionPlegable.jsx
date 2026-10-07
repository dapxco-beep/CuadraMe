import { useEffect, useId, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import Icono from './Icono'

// Sección colapsable que RECUERDA su estado (localStorage, con try/catch: en modo privado
// o sin almacenamiento simplemente arranca en su valor por defecto).
// El contenido NO se monta hasta que se abre por primera vez: una sección plegada no
// pide datos ni pinta nada. Una vez abierta, al plegar solo se oculta (conserva su estado).
//  - `resumen`: texto corto a la derecha del título, útil con la sección cerrada.
//  - `aviso`: pone un punto de atención junto al título (algo por resolver).
const CLAVE = 'cuadrame:inicio-secciones'

function leerTodo() {
  try {
    const v = JSON.parse(localStorage.getItem(CLAVE) || '{}')
    return v && typeof v === 'object' ? v : {}
  } catch {
    return {}
  }
}

export function leerEstadoSeccion(id, porDefecto = false) {
  const v = leerTodo()[id]
  return typeof v === 'boolean' ? v : porDefecto
}

function guardarEstadoSeccion(id, abierta) {
  try {
    localStorage.setItem(CLAVE, JSON.stringify({ ...leerTodo(), [id]: abierta }))
  } catch {
    /* sin almacenamiento: no se recuerda */
  }
}

export default function SeccionPlegable({ id, titulo, icono, resumen, aviso = false, abiertaPorDefecto = false, className = '', children }) {
  const uid = useId()
  const [abierta, setAbierta] = useState(() => leerEstadoSeccion(id, abiertaPorDefecto))
  const [montada, setMontada] = useState(abierta)
  useEffect(() => {
    if (abierta) setMontada(true)
  }, [abierta])

  function alternar() {
    const nueva = !abierta
    setAbierta(nueva)
    guardarEstadoSeccion(id, nueva)
  }

  return (
    <section className={className} data-seccion={id}>
      <h2 className="m-0">
        <button
          type="button"
          id={`${uid}-btn`}
          aria-expanded={abierta}
          aria-controls={`${uid}-cuerpo`}
          onClick={alternar}
          className="w-full min-h-[56px] px-4 flex items-center gap-3 text-left"
        >
          {icono && (
            <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
              <Icono icono={icono} tam="md" />
            </span>
          )}
          <span className="flex-1 min-w-0 t-h2 flex items-center gap-2">
            <span className="truncate">{titulo}</span>
            {aviso && <span className="w-2 h-2 rounded-full bg-accent shrink-0" aria-label="Hay algo por resolver" role="img" />}
          </span>
          {resumen && <span className="t-apoyo t-cifra shrink-0 max-w-[45%] truncate">{resumen}</span>}
          <Icono icono={ChevronDown} tam="md" className={`text-ink-soft transition-transform ${abierta ? 'rotate-180' : ''}`} />
        </button>
      </h2>
      {montada && (
        <div
          id={`${uid}-cuerpo`}
          role="region"
          aria-labelledby={`${uid}-btn`}
          hidden={!abierta}
          className="plegable-cuerpo px-4 pb-4 pt-1 border-t border-line"
        >
          {children}
        </div>
      )}
    </section>
  )
}
