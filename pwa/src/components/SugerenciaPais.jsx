import { useState } from 'react'
import { Globe2 } from 'lucide-react'
import { configPais } from '../lib/paises'
import { guardarPais, usePais } from '../lib/pais'

// Primer uso: si el navegador sugiere otro país (idioma o zona horaria; nunca la IP) y la persona
// aún no ha confirmado el suyo, lo preguntamos UNA vez. Quien está en Colombia no ve nada.
export default function SugerenciaPais() {
  const { pais, confirmado, cargado, sugerido } = usePais()
  const [oculto, setOculto] = useState(false)
  const [error, setError] = useState('')
  if (!cargado || confirmado || oculto || !sugerido || sugerido === pais) return null
  const c = configPais(sugerido)

  async function confirmar() {
    try {
      await guardarPais(sugerido)
    } catch {
      setError('No pudimos guardarlo ahora. Puedes cambiarlo después en tu perfil.')
    }
  }

  return (
    <section className="mx-5 mt-3 rounded-2xl bg-accent-soft p-3.5" role="note" data-testid="sugerencia-pais">
      <p className="text-sm font-semibold flex items-center gap-2">
        <Globe2 size={20} aria-hidden="true" /> ¿Estás en {c.nombre}?
      </p>
      <p className="text-xs text-ink mt-1">
        Así te mostramos tu moneda ({c.moneda}), tus bancos y los impuestos que aplican allá.
      </p>
      <div className="flex gap-2 mt-2.5">
        <button type="button" onClick={confirmar} className="rounded-xl bg-accent text-white text-sm font-semibold px-4 min-h-[44px]">
          Sí, estoy en {c.nombre}
        </button>
        <button type="button" onClick={() => setOculto(true)} className="text-sm font-semibold text-accent px-3 min-h-[44px]">
          No
        </button>
      </div>
      {error && <p role="alert" className="text-xs text-danger mt-2">{error}</p>}
    </section>
  )
}
