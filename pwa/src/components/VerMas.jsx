import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

// «Ver más»: deja lo principal a la vista y esconde el resto detrás de un botón.
// Los hijos se montan solo al abrir. `titulo` es lo que ofrece («los gráficos», «más detalles»).
export default function VerMas({ titulo = 'más detalles', abiertoPorDefecto = false, children }) {
  const [abierto, setAbierto] = useState(abiertoPorDefecto)
  return (
    <div>
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className="mx-5 mt-4 min-h-11 px-4 rounded-full border border-line bg-paper-raised text-sm font-semibold flex items-center gap-2"
      >
        {abierto ? `Ver menos` : `Ver ${titulo}`}
        <ChevronDown size={16} className={abierto ? 'rotate-180' : ''} aria-hidden="true" />
      </button>
      {abierto && children}
    </div>
  )
}
