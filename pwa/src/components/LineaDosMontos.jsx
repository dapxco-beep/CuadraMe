import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import Icono from './Icono'
import { formatCOP } from '../lib/format'
import { AVISO_LINEA_DOS_MONTOS, leerMontoEscrito } from '../lib/subidaMultiple'

/**
 * Una línea del extracto que traía DOS montos («Pago $697.534,97 -$474.542,00»): no sabemos cuál es el correcto y no lo
 * adivinamos. La persona elige uno de los montos que aparecen escritos en la línea o escribe el suyo; mientras no elija,
 * la línea no se marca ni se importa.
 *   it.montosAlt: los montos de la línea · valor: el monto elegido (o undefined) · onElegir(monto | null)
 */
export default function LineaDosMontos({ it, valor, onElegir, className = '' }) {
  const [texto, setTexto] = useState(valor ? String(valor).replace('.', ',') : '')
  return (
    <div className={`rounded-xl bg-accent-soft px-3 py-2.5 ${className}`} data-testid="linea-dos-montos">
      <p className="flex items-start gap-1.5 text-xs font-semibold text-accent" role="alert">
        <Icono icono={AlertTriangle} tam="sm" className="mt-px" />
        <span>{AVISO_LINEA_DOS_MONTOS}</span>
      </p>
      {it.montosAlt?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Montos que trae la línea">
          {it.montosAlt.map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={valor === m}
              onClick={() => {
                setTexto(String(m).replace('.', ','))
                onElegir(m)
              }}
              className={`min-h-11 rounded-xl border px-3.5 text-xs font-semibold ${valor === m ? 'bg-ink text-paper border-ink' : 'bg-paper-raised border-line text-ink'}`}
            >
              {formatCOP(m)}
            </button>
          ))}
        </div>
      )}
      <label className="mt-2 block text-xs text-ink-soft">
        O escribe el monto
        <input
          inputMode="decimal"
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value)
            onElegir(leerMontoEscrito(e.target.value))
          }}
          aria-label={`Monto de ${it.descripcion}`}
          placeholder="Ej. 474.542"
          className="mt-1 w-full min-h-11 rounded-xl border border-line bg-paper-raised px-3 text-sm text-ink"
        />
      </label>
      <p className="mt-1.5 text-[11px] leading-snug text-ink-soft">
        {valor ? `Se importará por ${formatCOP(valor)}.` : 'No se importa hasta que elijas el monto.'}
      </p>
    </div>
  )
}
