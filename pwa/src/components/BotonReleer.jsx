import { Loader2, RefreshCw } from 'lucide-react'
import { EXPLICACION_RELEER, TEXTO_ACCION } from '../lib/extractosVista'

/**
 * «Releer este extracto»: vuelve a leer un extracto ya procesado con las mejoras del lector, sin perder lo importado.
 * Muestra la explicación corta, el progreso («Leyendo...») y el resultado («Cambié 1 línea, agregué 0, conservé 2»).
 * `resultado` = { ok, texto } de la última vez; `nombre` es el extracto, para el nombre accesible del botón.
 */
export default function BotonReleer({ onReleer, ocupado = false, resultado = null, nombre = '' }) {
  return (
    <div className="mt-2" data-testid="releer-extracto">
      <p className="text-xs text-ink-soft leading-snug">{EXPLICACION_RELEER}</p>
      <button
        type="button"
        onClick={onReleer}
        disabled={ocupado}
        aria-label={`${TEXTO_ACCION.releer}${nombre ? `: ${nombre}` : ''}`}
        className="mt-1 inline-flex items-center gap-1.5 min-h-11 text-xs font-semibold text-accent disabled:opacity-50"
      >
        {ocupado ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}
        {ocupado ? 'Leyendo...' : TEXTO_ACCION.releer}
      </button>
      {resultado?.texto && (
        <p className={`text-xs leading-snug ${resultado.ok ? 'text-ink-soft' : 'text-danger'}`} role={resultado.ok ? 'status' : 'alert'} data-testid="resultado-releer">
          {resultado.texto}
        </p>
      )}
    </div>
  )
}
