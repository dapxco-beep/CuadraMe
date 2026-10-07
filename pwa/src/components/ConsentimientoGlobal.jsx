import { useEffect, useState } from 'react'
import ModalConsentimiento from './ModalConsentimiento'

export const EVENTO_RESUELTO = 'cuadrame:consentimiento-resuelto'
// Lo escucha quien pidió la acción (p. ej. Asistente) para reenviarla o descartarla. Si un
// oyente responde con `detail.atendido = true`, el aviso "vuelve a intentarlo" no se muestra.
let reenvioAtendido = false
function avisarResultado(finalidad, aceptado) {
  const detail = { finalidad, aceptado, atendido: false }
  window.dispatchEvent(new CustomEvent(EVENTO_RESUELTO, { detail }))
  reenvioAtendido = Boolean(detail.atendido) && aceptado
}

// Escucha el evento que api.js lanza cuando el backend responde "consentimiento_requerido"
// (por ejemplo, al usar el asistente o escanear una factura sin haber autorizado la IA) y
// muestra el consentimiento específico. Al autorizar, el usuario simplemente repite la acción.
export default function ConsentimientoGlobal() {
  const [finalidad, setFinalidad] = useState(null)
  const [hecho, setHecho] = useState(false)

  useEffect(() => {
    function alRequerir(e) {
      setHecho(false)
      setFinalidad(e.detail?.finalidad || null)
    }
    window.addEventListener('cuadrame:consentimiento', alRequerir)
    return () => window.removeEventListener('cuadrame:consentimiento', alRequerir)
  }, [])

  if (hecho) {
    return (
      <div role="status" className="fixed bottom-24 inset-x-6 z-[60] max-w-[440px] mx-auto rounded-2xl bg-ink text-paper text-sm px-4 py-3 text-center">
        Listo, gracias. Vuelve a intentarlo.
        <button className="ml-3 underline" onClick={() => setHecho(false)}>Cerrar</button>
      </div>
    )
  }
  if (!finalidad) return null
  return (
    <ModalConsentimiento
      finalidad={finalidad}
      origen="flujo_ia"
      onCancelar={() => {
        avisarResultado(finalidad, false)
        setFinalidad(null)
      }}
      onAceptado={() => {
        avisarResultado(finalidad, true)
        setFinalidad(null)
        // Si la pantalla que pidió la autorización reenvía sola su acción (Asistente), no hace
        // falta decirle al usuario que vuelva a intentarlo.
        setHecho(!reenvioAtendido)
      }}
    />
  )
}
