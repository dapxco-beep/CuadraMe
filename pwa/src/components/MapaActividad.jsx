import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { cuadriculaSemanas, rangoPeriodo } from '../lib/informe'
import SelectorPeriodo, { PERIODOS_ACTIVIDAD } from './SelectorPeriodo'

const DIAS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']

export function colorIntensidad(intensidad) {
  if (intensidad === 0) return 'var(--color-line)'
  if (intensidad < 0.25) return 'color-mix(in srgb, var(--color-accent) 30%, var(--color-paper-raised))'
  if (intensidad < 0.55) return 'color-mix(in srgb, var(--color-accent) 60%, var(--color-paper-raised))'
  if (intensidad < 0.85) return 'var(--color-accent)'
  return 'var(--color-danger)'
}

function textoDia(dia) {
  const f = new Date(`${dia}T00:00:00`)
  return f.toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' })
}

// Mapa de calor del gasto diario con rango configurable (por defecto 5 semanas).
// Calendario lunes-domingo con el número del día dentro de cada celda; al tocar una
// celda se ve el gasto de ese día. Los datos vienen de /informes/diario (regla
// contable aplicada: sin pagos de tarjeta ni traslados).
export default function MapaActividad() {
  const { fmt } = useBloqueo()
  const [valor, setValor] = useState({ periodo: '5_semanas', ...rangoPeriodo('5_semanas') })
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(false)
  const [sel, setSel] = useState(null)

  useEffect(() => {
    let activo = true
    setError(false)
    setSel(null)
    api.gastoDiario(valor.desde, valor.hasta)
      .then((d) => activo && setDatos(d))
      .catch(() => activo && setError(true))
    return () => {
      activo = false
    }
  }, [valor.desde, valor.hasta])

  const dias = datos?.dias ?? []
  const semanas = useMemo(() => cuadriculaSemanas(dias), [dias])
  const max = Math.max(1, ...dias.map((d) => d.gasto))
  const conNumero = semanas.length <= 12
  const seleccionado = dias.find((d) => d.dia === sel)

  return (
    <section className="mx-6 mt-4">
      <p className="text-[11px] font-bold text-ink-soft uppercase tracking-wide mb-2.5">Tu gasto día a día</p>
      <SelectorPeriodo opciones={PERIODOS_ACTIVIDAD} valor={valor} onChange={setValor} etiqueta="Periodo del gasto diario" />

      {error && <p role="alert" className="text-xs text-danger mt-3">No se pudo cargar el gasto diario.</p>}

      {dias.length > 0 && (
        <div className="mt-4 card-marca bg-paper-raised border border-line p-3.5">
          <div className="grid grid-cols-7 gap-1.5 mb-1.5" aria-hidden="true">
            {DIAS.map((d) => (
              <span key={d} className="text-center text-[10px] font-semibold text-ink-soft">{d}</span>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1.5" role="group" aria-label="Gasto por día">
            {semanas.flat().map((d, i) =>
              d ? (
                <button
                  key={d.dia}
                  type="button"
                  onClick={() => setSel(sel === d.dia ? null : d.dia)}
                  aria-pressed={sel === d.dia}
                  aria-label={`${textoDia(d.dia)}: ${fmt(d.gasto)}`}
                  className={`aspect-square min-h-[38px] rounded-[8px] pop-in flex items-center justify-center text-[11px] font-medium ${sel === d.dia ? 'ring-2 ring-ink' : ''}`}
                  style={{
                    background: colorIntensidad(d.gasto / max),
                    animationDelay: `${Math.min(i, 20) * 12}ms`,
                    color: d.gasto / max >= 0.55 ? '#fff' : 'var(--color-ink)',
                  }}
                >
                  {conNumero ? Number(d.dia.slice(8)) : ''}
                </button>
              ) : (
                <span key={`v-${i}`} aria-hidden="true" />
              )
            )}
          </div>
          <p className="text-xs mt-3 min-h-[18px]" aria-live="polite">
            {seleccionado ? (
              <>
                <span className="capitalize">{textoDia(seleccionado.dia)}</span>: <b>{fmt(seleccionado.gasto)}</b>
              </>
            ) : (
              <span className="text-ink-soft">Total del periodo: <b className="text-ink">{fmt(datos.total)}</b> · toca un día para ver su gasto</span>
            )}
          </p>
          <div className="flex items-center gap-1.5 mt-2 text-[10px] text-ink-soft">
            <span>Menos</span>
            {[0, 0.2, 0.4, 0.7, 1].map((v) => (
              <span key={v} className="w-3 h-3 rounded-[3px]" style={{ background: colorIntensidad(v) }} />
            ))}
            <span>Más</span>
          </div>
        </div>
      )}
    </section>
  )
}
