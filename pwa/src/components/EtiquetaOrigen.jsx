import { etiquetaOrigen, faltaConfirmarExtracto, textoConfirmado } from '../lib/canales'

// Píldora pequeña con la vía por la que llegó un movimiento («correo», «a mano»…) y, si lo confirmaron
// otras vías, «confirmado por correo + extracto». No pinta nada si el servidor no mandó el origen.
export default function EtiquetaOrigen({ origen, canales, className = '', soloAvisos = false }) {
  const et = etiquetaOrigen(origen)
  if (!et) return null
  const conf = textoConfirmado(origen, canales)
  if (soloAvisos && !conf && !faltaConfirmarExtracto(origen, canales)) return null
  return (
    <span className={`inline-flex flex-wrap items-center gap-1 ${className}`} data-testid="etiqueta-origen">
      {!soloAvisos && <span className="rounded-full bg-paper border border-line text-ink-soft text-[11px] font-medium px-2 py-0.5">{et}</span>}
      {conf && <span className="rounded-full bg-cuadra-soft text-cuadra text-[11px] font-semibold px-2 py-0.5">{conf}</span>}
      {faltaConfirmarExtracto(origen, canales) && (
        <span className="rounded-full bg-accent-soft text-accent text-[11px] font-semibold px-2 py-0.5" data-testid="falta-confirmar-extracto">
          Falta confirmar con el extracto
        </span>
      )}
    </span>
  )
}
