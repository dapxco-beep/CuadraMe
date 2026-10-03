import { Eye, EyeOff } from 'lucide-react'
import { useBloqueo } from '../lib/BloqueoContext'

// Ojo para ocultar/mostrar saldos. La preferencia se recuerda (localStorage) y
// es global: ocultar en Inicio también oculta en Cuentas.
export default function BotonOjo({ className = '' }) {
  const { ocultarSaldos, alternarOcultar } = useBloqueo()
  const Icono = ocultarSaldos ? EyeOff : Eye
  return (
    <button
      type="button"
      onClick={alternarOcultar}
      aria-pressed={ocultarSaldos}
      aria-label={ocultarSaldos ? 'Mostrar saldos' : 'Ocultar saldos'}
      className={`w-9 h-9 rounded-full bg-paper-raised border border-line flex items-center justify-center ${className}`}
    >
      <Icono size={17} className="text-ink-soft" />
    </button>
  )
}
