import { Check } from 'lucide-react'
import { ETIQUETA_CANAL, textoCanales } from '../lib/canales'

// Insignia «Registrado desde: atajo + correo + extracto» del detalle de un movimiento.
// Cada canal que confirmó el movimiento sale como una píldora; con 2 o más canales se nota que
// el banco mismo lo corrobora. No dibuja nada si el servidor no mandó canales (movimientos viejos).
export default function InsigniaCanales({ canales }) {
  const lista = (canales || []).filter((c) => ETIQUETA_CANAL[c])
  if (lista.length === 0) return null
  return (
    <div data-testid="insignia-canales" className="px-4 py-3.5">
      <p className="text-xs text-ink-soft">Registrado desde</p>
      <p className="sr-only">Registrado desde: {textoCanales(lista)}</p>
      <div className="flex flex-wrap items-center gap-1.5 mt-1.5" aria-hidden="true">
        {['manual', 'atajo', 'correo', 'extracto', 'importacion']
          .filter((c) => lista.includes(c))
          .map((c) => (
            <span
              key={c}
              className="inline-flex items-center gap-1 rounded-full bg-cuadra-soft text-cuadra text-xs font-semibold px-2.5 py-1"
            >
              <Check size={16} /> {ETIQUETA_CANAL[c]}
            </span>
          ))}
      </div>
      {lista.length > 1 && (
        <p className="text-xs text-ink-soft mt-1.5">Varios canales avisaron de este gasto y se juntaron en un solo movimiento.</p>
      )}
    </div>
  )
}
