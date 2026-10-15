import { Link } from 'react-router-dom'

// Una línea por cuenta con el estado del cuadre con el banco (viene de GET /conciliacion/cuadre/resumen).
// ✓ «Cuadra a junio» · ✕ «No cuadra en junio (dif. $800.000)» · «Sin saldo del extracto para cuadrar».
// Siempre dice el motivo y qué hacer; toca para ir al cuadre mes a mes.
const TONO = {
  cuadra: 'text-cuadra',
  no_cuadra: 'text-danger',
  sin_saldo: 'text-ink-soft',
  sin_extractos: 'text-ink-soft',
}
const MARCA = { cuadra: '✓', no_cuadra: '✕', sin_saldo: '•', sin_extractos: '•' }

export default function LineaCuadre({ item, className = '' }) {
  if (!item) return null
  return (
    <Link
      to="/sincronizacion"
      state={{ abrir: 'extractos' }}
      data-testid="linea-cuadre"
      data-estado={item.estado}
      className={`block rounded-xl border border-line px-3 py-2 min-h-[44px] ${className}`}
    >
      <p className={`text-xs font-semibold ${TONO[item.estado] || ''}`}>
        <span aria-hidden="true">{MARCA[item.estado]} </span>
        {item.texto}
      </p>
      {item.motivo && <p className="text-[11px] text-ink-soft mt-0.5">{item.motivo}</p>}
      {item.accion && <p className="text-[11px] font-semibold text-accent mt-0.5">{item.accion}</p>}
    </Link>
  )
}
