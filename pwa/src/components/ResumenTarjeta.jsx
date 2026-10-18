import { CheckCircle2, AlertTriangle } from 'lucide-react'
import Icono from './Icono'
import { filasResumenTarjeta } from '../lib/subidaMultiple'

/**
 * Extracto de la tarjeta de Nu: arriba, si lo leído suma lo que dice el extracto («Leí 17 líneas y suman…»), y debajo
 * los datos del resumen de la página 1 (deuda a pagar, pago mínimo, fecha límite, cupo…). Siempre dice cuántas líneas leyó.
 */
export default function ResumenTarjeta({ mensaje, completa, resumen, className = '' }) {
  if (!mensaje && !resumen) return null
  const filas = filasResumenTarjeta(resumen)
  return (
    <div className={`rounded-2xl border border-line bg-paper px-3.5 py-2.5 ${className}`} data-testid="resumen-tarjeta">
      {mensaje && (
        <p
          className={`flex items-start gap-1.5 text-xs font-semibold ${completa === false ? 'text-danger' : 'text-cuadra'}`}
          role={completa === false ? 'alert' : 'status'}
          data-testid="mensaje-lectura"
        >
          <Icono icono={completa === false ? AlertTriangle : CheckCircle2} tam="sm" className="mt-px" />
          <span>{mensaje}</span>
        </p>
      )}
      {filas.length > 0 && (
        <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]" data-testid="datos-resumen-tarjeta">
          {filas.map(([k, v]) => (
            <div key={k} className="min-w-0">
              <dt className="text-ink-soft">{k}</dt>
              <dd className="font-semibold break-words">{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}
