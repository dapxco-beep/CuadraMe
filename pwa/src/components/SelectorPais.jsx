import { useState } from 'react'
import { Check, Globe2 } from 'lucide-react'
import Bandera from './Bandera'
import { paisesDisponibles } from '../lib/paises'
import { guardarPais, usePais } from '../lib/pais'

// País de la persona: define moneda, bancos y qué funciones de impuestos se muestran.
// Se monta en Perfil (editable) y, como sugerencia, en el primer uso (SugerenciaPais).
export default function SelectorPais({ onGuardado }) {
  const { pais, config } = usePais()
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function elegir(codigo) {
    if (codigo === pais || guardando) return
    setGuardando(true)
    setError('')
    try {
      await guardarPais(codigo)
      onGuardado?.(codigo)
    } catch {
      setError('No pudimos guardar tu país. Revisa tu conexión e inténtalo de nuevo.')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section aria-label="País" data-testid="selector-pais">
      <h2 className="text-[15px] font-semibold flex items-center gap-2">
        <Globe2 size={20} aria-hidden="true" /> Tu país
      </h2>
      <p className="text-xs text-ink-soft mt-1">
        Define tu moneda, tus bancos y los impuestos que te mostramos. Ahora: <b className="text-ink">{config.nombre}</b> ({config.moneda}).
      </p>
      <div className="grid grid-cols-2 gap-2 mt-3" role="group" aria-label="Elige tu país">
        {paisesDisponibles().map((c) => (
          <button
            key={c.codigo}
            type="button"
            aria-pressed={pais === c.codigo}
            disabled={guardando}
            onClick={() => elegir(c.codigo)}
            className={`flex items-center gap-2 rounded-2xl border px-3 py-2.5 text-sm font-medium min-h-[44px] text-left transition-colors ${
              pais === c.codigo ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
            }`}
          >
            <Bandera pais={c.codigo} />
            <span className="flex-1">{c.nombre}</span>
            {pais === c.codigo && <Check size={16} aria-hidden="true" />}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="text-xs text-danger mt-2">{error}</p>}
    </section>
  )
}
