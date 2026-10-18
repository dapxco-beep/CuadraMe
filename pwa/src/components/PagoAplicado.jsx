import { Info } from 'lucide-react'
import Icono from './Icono'
import { textoPagoAplicado } from '../lib/subidaMultiple'

/**
 * Tarjeta informativa del «Pago» de un extracto de tarjeta: cómo se aplicó ese pago (capital, intereses, cargos)
 * y a qué dos montos se aplicó. El pago importable es la fila de arriba (por el monto del pago); esto solo explica.
 */
export default function PagoAplicado({ detalle, aviso, className = '' }) {
  const texto = textoPagoAplicado(detalle)
  if (!texto) return null
  return (
    <div className={`rounded-xl bg-accent-soft px-3 py-2.5 ${className}`} data-testid="pago-aplicado">
      <p className="flex items-start gap-1.5 text-xs font-semibold text-accent">
        <Icono icono={Info} tam="sm" className="mt-px" />
        <span>{texto.principal}</span>
      </p>
      {texto.aplicado && <p className="mt-1 text-[11px] leading-snug text-ink-soft" data-testid="pago-se-aplico">{texto.aplicado}</p>}
      {aviso && <p className="mt-1.5 text-[11px] leading-snug text-ink-soft" role="status" data-testid="aviso-pago-tarjeta">{aviso}</p>}
    </div>
  )
}
