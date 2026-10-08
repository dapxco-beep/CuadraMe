import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CircleHelp } from 'lucide-react'
import Hoja from './Hoja'
import Icono from './Icono'
import { AVISO_EDUCATIVO, leccionPorId, terminoPorId } from '../lib/aprende'

/**
 * Ayudita «¿qué es esto?»: un botón pequeño junto a un término (cupo, corte, pago mínimo…) que abre
 * la definición del glosario de «Aprende». Uso: <Ayudita termino="cupo" />.
 *
 * - `termino` es el id del glosario (lib/aprende.js). Si no existe, no pinta nada (nunca rompe la pantalla).
 * - El área táctil es de 44 px aunque el ícono sea de 16: los márgenes negativos evitan que agrande la fila.
 * - Va dentro de otras hojas (detalle de cuenta), por eso abre su hoja en una capa más alta.
 */
export default function Ayudita({ termino, className = '' }) {
  const [abierta, setAbierta] = useState(false)
  const t = terminoPorId(termino)
  if (!t) return null
  const leccion = t.leccion ? leccionPorId(t.leccion) : null

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setAbierta(true)
        }}
        aria-label={`¿Qué es ${t.termino}?`}
        aria-haspopup="dialog"
        className={`inline-flex items-center justify-center min-w-11 min-h-11 -m-3 align-middle text-ink-soft ${className}`}
      >
        <Icono icono={CircleHelp} tam="sm" />
      </button>
      {abierta && (
        <Hoja onCerrar={() => setAbierta(false)} titulo={t.termino} capa="z-[70]" historial={false} testId="ayudita-hoja">
          {({ cerrar }) => (
            <div>
              <p className="t-kicker text-ink-soft">¿Qué es esto?</p>
              <h2 className="text-lg font-semibold mt-1">{t.termino}</h2>
              <p className="t-cuerpo mt-2">{t.definicion}</p>
              <p className="t-apoyo mt-3">{AVISO_EDUCATIVO}</p>
              <div className="flex gap-2 mt-4">
                {leccion && (
                  <Link to={`/aprende?l=${leccion.id}`} onClick={cerrar} className="btn btn-suave btn-sm">
                    Aprender más
                  </Link>
                )}
                <button type="button" onClick={cerrar} className="btn btn-secundario btn-sm">
                  Entendido
                </button>
              </div>
            </div>
          )}
        </Hoja>
      )}
    </>
  )
}
