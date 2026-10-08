import { RefreshCw, WifiOff } from 'lucide-react'
import Cuadri from './Cuadri'
import Icono from '../components/Icono'
import { frase } from '../lib/cuadri'

/**
 * Error amable: Cuadri preocupado (o sorprendido) + qué pasó en llano + una acción clara.
 * Sirve para fallos de carga y para «sin conexión». Sin culpar a la persona ni usar jerga.
 * Si Cuadri está apagado en Perfil, queda solo el texto y el botón.
 *  - sinConexion: usa el ícono de wifi y el texto por defecto de falta de internet.
 *  - detalle: el mensaje del servidor, si lo hay (se muestra pequeño bajo el texto).
 */
export default function ErrorAmable({ titulo, texto, detalle, sinConexion = false, accion = 'Reintentar', onAccion, className = '' }) {
  const t = titulo || (sinConexion ? 'Sin conexión por ahora' : 'Algo no salió bien')
  const d = texto || frase(sinConexion ? 'sinConexion' : 'errorGenerico')
  return (
    <div role="alert" data-testid="error-amable" className={`flex-1 flex flex-col items-center justify-center gap-2 px-8 text-center ${className}`}>
      <Cuadri pose={sinConexion ? 'preocupado' : 'sorprendido'} size={92} />
      <h2 className="text-base font-semibold">
        {sinConexion && <Icono icono={WifiOff} tam="sm" className="inline mr-1.5 -mt-0.5 text-ink-soft" />}
        {t}
      </h2>
      <p className="t-cuerpo text-ink-soft max-w-xs">{d}</p>
      {detalle && <p className="t-apoyo max-w-xs">{detalle}</p>}
      {onAccion && (
        <button type="button" onClick={onAccion} className="btn btn-suave mt-2 inline-flex items-center gap-1.5">
          <Icono icono={RefreshCw} tam="sm" /> {accion}
        </button>
      )}
    </div>
  )
}
