import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { hayVersionNueva, leerVersionPublicada, recargarConVersionNueva } from '../lib/version'

const CADA_MS = 30 * 60 * 1000

// Franja discreta cuando ya hay una compilación más nueva desplegada. NUNCA recarga sola:
// la persona puede estar escribiendo; el botón «Actualizar» es quien recarga.
export default function FranjaVersionNueva() {
  const [nueva, setNueva] = useState(false)

  useEffect(() => {
    let vivo = true
    async function revisar() {
      const pub = await leerVersionPublicada()
      if (vivo && hayVersionNueva(pub)) setNueva(true)
    }
    const alVolver = () => {
      if (document.visibilityState === 'visible') revisar()
    }
    document.addEventListener('visibilitychange', alVolver)
    const t = setInterval(revisar, CADA_MS)
    revisar()
    return () => {
      vivo = false
      document.removeEventListener('visibilitychange', alVolver)
      clearInterval(t)
    }
  }, [])

  if (!nueva) return null
  return (
    <div role="status" className="mx-4 mt-2 flex items-center justify-between gap-3 rounded-xl bg-accent-soft px-3 py-2 text-sm">
      <span>Hay una versión nueva</span>
      <button type="button" onClick={recargarConVersionNueva} className="inline-flex items-center gap-1.5 font-medium text-accent min-h-[36px]">
        <RefreshCw size={16} aria-hidden="true" />
        Actualizar
      </button>
    </div>
  )
}
