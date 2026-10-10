import { useEffect, useState } from 'react'
import { WifiOff } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'
import { api } from '../lib/api'
import { enviarPendientes, pendientesDe } from '../lib/colaOffline'

// Franja discreta cuando no hay señal (o cuando lo que se ve es la última copia guardada), y envío
// de los gastos que se guardaron sin conexión en cuanto vuelve la red. No bloquea nada.
export default function AvisoSinConexion() {
  const auth = useAuth()
  const uid = auth?.usuario?.id
  const [sinRed, setSinRed] = useState(() => typeof navigator !== 'undefined' && navigator.onLine === false)
  const [pendientes, setPendientes] = useState(() => (uid ? pendientesDe(uid).length : 0))

  useEffect(() => {
    const caer = () => setSinRed(true)
    const volver = () => setSinRed(false)
    window.addEventListener('offline', caer)
    window.addEventListener('online', volver)
    window.addEventListener('cuadrame:datos-guardados', caer)
    window.addEventListener('cuadrame:conexion-ok', volver)
    return () => {
      window.removeEventListener('offline', caer)
      window.removeEventListener('online', volver)
      window.removeEventListener('cuadrame:datos-guardados', caer)
      window.removeEventListener('cuadrame:conexion-ok', volver)
    }
  }, [])

  // Envía lo pendiente al abrir, al volver la red y cuando se encola algo nuevo estando con señal.
  useEffect(() => {
    if (!uid) return undefined
    let vivo = true
    const enviar = async () => {
      if (typeof navigator !== 'undefined' && navigator.onLine === false) return
      if (pendientesDe(uid).length === 0) return
      const r = await enviarPendientes(uid, (d) => api.crearMovimiento(d))
      if (!vivo) return
      setPendientes(r.quedan)
      if (r.enviados > 0) {
        window.dispatchEvent(new CustomEvent('cuadrame:movimientos-cambio'))
        const mensaje =
          r.enviados === 1
            ? 'Se envió el movimiento que guardaste sin conexión.'
            : `Se enviaron ${r.enviados} movimientos que guardaste sin conexión.`
        window.dispatchEvent(new CustomEvent('cuadrame:aviso', { detail: { mensaje, tipo: 'info' } }))
      }
    }
    const alEncolar = () => {
      setPendientes(pendientesDe(uid).length)
      enviar()
    }
    enviar()
    window.addEventListener('online', enviar)
    window.addEventListener('cuadrame:cola-cambio', alEncolar)
    return () => {
      vivo = false
      window.removeEventListener('online', enviar)
      window.removeEventListener('cuadrame:cola-cambio', alEncolar)
    }
  }, [uid])

  if (!sinRed && pendientes === 0) return null
  return (
    <div
      role="status"
      data-testid="aviso-sin-conexion"
      className="mx-4 mt-2 rounded-xl bg-paper-raised border border-line px-3 py-2 flex items-center gap-2 text-xs text-ink-soft"
    >
      <WifiOff size={16} aria-hidden="true" className="shrink-0" />
      <span>
        {sinRed ? 'Sin conexión: ves lo último que cargó.' : 'Enviando lo que guardaste sin conexión…'}
        {pendientes > 0 &&
          ` ${pendientes === 1 ? '1 movimiento espera' : `${pendientes} movimientos esperan`} señal para enviarse.`}
      </span>
    </div>
  )
}
