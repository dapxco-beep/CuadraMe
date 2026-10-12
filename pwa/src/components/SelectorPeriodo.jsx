import { useState } from 'react'
import { Chip } from './ui'
import { aISO, rangoPeriodo, rangoValido } from '../lib/informe'

export const PERIODOS_INFORME = [
  { id: 'este_mes', label: 'Este mes' },
  { id: 'mes_pasado', label: 'Mes pasado' },
  { id: '3_meses', label: '3 meses' },
  { id: 'anio', label: 'Este año' },
  { id: 'rango', label: 'Personalizado' },
]

export const PERIODOS_ACTIVIDAD = [
  { id: '7_dias', label: '7 días' },
  { id: '5_semanas', label: '5 semanas' },
  { id: '30_dias', label: '30 días' },
  { id: 'este_mes', label: 'Este mes' },
  { id: 'rango', label: 'Personalizado' },
]

// Chips de periodo + dos selectores de fecha nativos (en móvil abren el calendario
// del sistema, que es lo más cómodo). Emite { periodo, desde, hasta } siempre con
// fechas AAAA-MM-DD; el rango personalizado solo se emite cuando es válido.
export default function SelectorPeriodo({ opciones = PERIODOS_INFORME, valor, onChange, maxDias = 400, etiqueta = 'Periodo' }) {
  const hoy = aISO(new Date())
  const [borrador, setBorrador] = useState({ desde: valor?.desde || hoy, hasta: valor?.hasta || hoy })
  const esRango = valor?.periodo === 'rango'
  const valido = rangoValido(borrador.desde, borrador.hasta, maxDias)

  function elegir(id) {
    if (id === 'rango') {
      onChange({ periodo: 'rango', ...(rangoValido(borrador.desde, borrador.hasta, maxDias) ? borrador : rangoPeriodo('30_dias')) })
      if (!rangoValido(borrador.desde, borrador.hasta, maxDias)) setBorrador(rangoPeriodo('30_dias'))
    } else {
      onChange({ periodo: id, ...rangoPeriodo(id) })
    }
  }

  function cambiar(campo, v) {
    const nuevo = { ...borrador, [campo]: v }
    setBorrador(nuevo)
    if (rangoValido(nuevo.desde, nuevo.hasta, maxDias)) onChange({ periodo: 'rango', ...nuevo })
  }

  return (
    <div>
      <div className="flex gap-1.5 overflow-x-auto no-scrollbar -mx-6 px-6" role="group" aria-label={etiqueta}>
        {opciones.map((o) => (
          <Chip key={o.id} activo={valor?.periodo === o.id} onClick={() => elegir(o.id)} className="shrink-0 text-xs font-semibold">
            {o.label}
          </Chip>
        ))}
      </div>
      {esRango && (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <label className="text-[11px] font-semibold text-ink-soft">
            Desde
            <input
              type="date"
              value={borrador.desde}
              max={borrador.hasta || hoy}
              onChange={(e) => cambiar('desde', e.target.value)}
              className="mt-1 w-full rounded-xl border border-line bg-paper-raised px-3 py-3 text-sm text-ink min-h-[44px]"
            />
          </label>
          <label className="text-[11px] font-semibold text-ink-soft">
            Hasta
            <input
              type="date"
              value={borrador.hasta}
              min={borrador.desde}
              max={hoy}
              onChange={(e) => cambiar('hasta', e.target.value)}
              className="mt-1 w-full rounded-xl border border-line bg-paper-raised px-3 py-3 text-sm text-ink min-h-[44px]"
            />
          </label>
          {!valido && (
            <p role="alert" className="col-span-2 text-xs text-danger">
              Elige un rango válido (la fecha final no puede ser anterior a la inicial, máximo {maxDias} días).
            </p>
          )}
        </div>
      )}
    </div>
  )
}
