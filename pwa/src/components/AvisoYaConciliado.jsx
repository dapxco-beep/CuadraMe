import { nombreMes, textoCruzados } from '../lib/sincronizacion'

/**
 * Aviso (no bloquea) cuando el archivo que se subió es de un periodo+cuenta que ya
 * estaba conciliado. El usuario decide si lo revisa de nuevo: no se duplica nada
 * porque cada movimiento se compara por huella antes de importarse.
 * `info` es lo que devuelve el servidor: { mes: '2026-09', cruzados: n }.
 */
export default function AvisoYaConciliado({ info, cuenta, className = '' }) {
  if (!info) return null
  const mes = nombreMes(info.mes)
  return (
    <div role="status" className={`rounded-2xl bg-accent-soft p-3.5 ${className}`} data-testid="aviso-ya-conciliado">
      <p className="text-xs font-semibold text-ink">
        Este periodo{cuenta ? ` de ${cuenta}` : ''} ya lo revisamos con tu extracto: ¿quieres revisarlo otra vez?
      </p>
      <p className="text-xs text-ink-soft mt-0.5">
        {mes ? `${mes[0].toUpperCase()}${mes.slice(1)}` : 'Ese mes'}
        {info.cruzados ? ` · ${textoCruzados(info.cruzados)}` : ''}. Puedes seguir: lo que ya registraste no se duplica.
      </p>
    </div>
  )
}
