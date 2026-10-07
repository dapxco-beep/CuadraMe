import { useState } from 'react'
import { CreditCard } from 'lucide-react'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'

// "Tu extracto dice: cupo $X, pago total $Y, vence el D. ¿Actualizar tu tarjeta?"
// Es solo una PROPUESTA: la tarjeta no cambia hasta que el cliente pulsa "Aplicar".
// Se usa donde se procesa el extracto de una tarjeta de crédito (Conciliación y, con la
// misma respuesta de /conciliacion/procesar, Sincronización).
//   propuesta: { cambios, datos, texto }  (viene de propuesta_tarjeta)
export default function PropuestaTarjeta({ propuesta, cuentaId, className = '' }) {
  const { recargar } = useCuentas()
  const [estado, setEstado] = useState('propuesta') // propuesta | aplicada | descartada
  const [error, setError] = useState('')
  const [aplicando, setAplicando] = useState(false)
  if (!propuesta || estado === 'descartada') return null

  async function aplicar() {
    setError('')
    setAplicando(true)
    try {
      const d = propuesta.datos || {}
      await api.aplicarExtractoTarjeta(cuentaId, {
        ...propuesta.cambios,
        ...(d.cupo_disponible != null ? { cupo_disponible: d.cupo_disponible } : {}),
        ...(d.pago_total != null ? { pago_total: d.pago_total } : {}),
        ...(d.pago_minimo != null ? { pago_minimo: d.pago_minimo } : {}),
        ...(d.fecha_limite_pago ? { fecha_limite_pago: d.fecha_limite_pago } : {}),
        ...(d.fecha_corte ? { fecha_corte: d.fecha_corte } : {}),
      })
      await recargar?.()
      setEstado('aplicada')
    } catch (err) {
      setError(err.message || 'No se pudo actualizar la tarjeta')
    } finally {
      setAplicando(false)
    }
  }

  return (
    <div className={`rounded-2xl border border-line bg-paper-raised p-4 ${className}`} role="region" aria-label="Datos de tu tarjeta" data-testid="propuesta-tarjeta">
      <div className="flex items-start gap-2.5">
        <CreditCard size={20} className="text-accent shrink-0 mt-0.5" />
        {estado === 'aplicada' ? (
          <p role="status" className="text-sm font-semibold text-accent">Listo: actualizamos tu tarjeta.</p>
        ) : (
          <p className="text-sm">{propuesta.texto}</p>
        )}
      </div>
      {estado === 'propuesta' && (
        <>
          {error && <p role="alert" className="text-xs text-danger mt-2">{error}</p>}
          <div className="flex gap-2 mt-3">
            <button
              onClick={aplicar}
              disabled={aplicando}
              className="flex-1 bg-accent text-white font-semibold rounded-2xl py-3 text-sm disabled:opacity-60 min-h-[44px]"
            >
              {aplicando ? 'Aplicando...' : 'Aplicar'}
            </button>
            <button onClick={() => setEstado('descartada')} className="px-4 rounded-2xl border border-line text-sm text-ink-soft min-h-[44px]">
              Ahora no
            </button>
          </div>
        </>
      )}
    </div>
  )
}
