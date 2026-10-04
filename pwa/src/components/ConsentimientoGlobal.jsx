import { useEffect, useState } from 'react'
import ModalConsentimiento from './ModalConsentimiento'

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
      onCancelar={() => setFinalidad(null)}
      onAceptado={() => {
        setFinalidad(null)
        setHecho(true)
      }}
    />
  )
}
