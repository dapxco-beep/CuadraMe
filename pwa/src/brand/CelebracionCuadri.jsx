import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import Cuadri from './Cuadri'
import Icono from '../components/Icono'
import { leerMostrarCuadri, marcarCelebrado, yaCelebrado } from '../lib/cuadri'

/**
 * Celebración breve de Cuadri: aparece abajo, no bloquea nada (el contenedor deja pasar los toques),
 * se puede cerrar y se va sola a los 7 s. Cada `id` se celebra UNA sola vez por dispositivo
 * (se guarda solo el id), y no sale si la persona apagó «Mostrar a Cuadri».
 *
 * Úsala con una condición real: <CelebracionCuadri id="meta-12" cuando={meta.completada} .../>
 */
export default function CelebracionCuadri({ id, cuando = true, titulo, texto, ms = 7000 }) {
  const [abierta, setAbierta] = useState(false)
  const marcado = useRef(false)

  // Al cumplirse la condición por primera vez: se muestra y se anota de una vez (aunque recargue, no repite).
  useEffect(() => {
    if (!cuando || marcado.current || !leerMostrarCuadri() || yaCelebrado(id)) return
    marcado.current = true
    marcarCelebrado(id)
    setAbierta(true)
  }, [cuando, id])

  useEffect(() => {
    if (!abierta) return undefined
    const t = setTimeout(() => setAbierta(false), ms)
    return () => clearTimeout(t)
  }, [abierta, ms])

  if (!abierta) return null
  return (
    <div className="fixed inset-x-0 z-40 px-4 pointer-events-none" style={{ bottom: 'calc(env(safe-area-inset-bottom) + 88px)' }}>
      <div
        role="status"
        data-testid="celebracion-cuadri"
        className="cuadri-celebra pointer-events-auto max-w-md mx-auto card-marca bg-paper-raised border border-line shadow-lg flex items-center gap-3 pl-3 pr-1 py-2"
      >
        <Cuadri pose="celebrando" size={56} />
        <div className="flex-1 min-w-0 py-1">
          <p className="text-sm font-semibold">{titulo}</p>
          {texto && <p className="t-apoyo mt-0.5">{texto}</p>}
        </div>
        <button type="button" onClick={() => setAbierta(false)} aria-label="Cerrar aviso" className="shrink-0 w-11 h-11 flex items-center justify-center text-ink-soft">
          <Icono icono={X} tam="sm" />
        </button>
      </div>
    </div>
  )
}
