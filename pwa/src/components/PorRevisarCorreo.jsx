import { Mail } from 'lucide-react'
import CorreosPorRevisar from './CorreosPorRevisar'

/**
 * Sección «Por revisar · N del correo» de la pantalla Movimientos: las tarjetas de lo que llegó por
 * Gmail, con su fecha, para aprobar, editar o descartar. Al aprobar pasa a la lista normal.
 *   correos: GET /correos/pendientes   ·   onResuelto(correo, aprobado)
 */
export default function PorRevisarCorreo({ correos, onResuelto, onCuentaCreada, onRecargar, className = '' }) {
  if (!correos?.length) return null
  return (
    <section aria-label="Por revisar del correo" className={`rounded-3xl bg-accent-soft/40 border border-accent/30 p-4 ${className}`} data-testid="por-revisar-correo">
      <h2 className="flex items-center gap-2 text-[15px] font-semibold">
        <Mail size={20} className="text-accent shrink-0" aria-hidden="true" />
        Por revisar · {correos.length} del correo
      </h2>
      <p className="text-xs text-ink-soft mt-0.5 mb-3">
        Los leí de las notificaciones de tu banco. Revisa la fecha y apruébalos: así pasan a tu lista.
      </p>
      <CorreosPorRevisar correos={correos} onResuelto={onResuelto} onCuentaCreada={onCuentaCreada} onRecargar={onRecargar} />
    </section>
  )
}
