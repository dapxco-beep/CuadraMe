import { Info } from 'lucide-react'
import Icono from './Icono'
import { textoResumenFactura } from '../lib/subidaMultiple'

/**
 * Tarjeta informativa de la fila «resumen de la factura anterior» del extracto de una tarjeta.
 * No es una línea que se importe: dice cuánto era la factura, cuánto pagaste y cuánto quedó pendiente.
 * El pago de lo que pagaste es la fila importable que va justo arriba.
 */
export default function ResumenFacturaAnterior({ resumen, aviso, className = '' }) {
  if (!resumen) return null
  return (
    <div className={`rounded-xl bg-accent-soft px-3 py-2.5 ${className}`} data-testid="resumen-factura-anterior">
      <p className="flex items-start gap-1.5 text-xs font-semibold text-accent">
        <Icono icono={Info} tam="sm" className="mt-px" />
        <span>{textoResumenFactura(resumen)}</span>
      </p>
      {aviso && <p className="mt-1.5 text-[11px] leading-snug text-ink-soft" role="status" data-testid="aviso-pago-factura">{aviso}</p>}
    </div>
  )
}
