import { colorEstado, posicionesBarra } from '../lib/planificacion'

// Barra de gasto del periodo con un marcador (▼) donde cerrarías al ritmo actual.
// Si el marcador llega al borde derecho y `desborda`, vas a pasarte del límite.
export default function BarraProyeccion({ item, animar = true }) {
  const { usado, marcador, desborda } = posicionesBarra(item)
  const color = colorEstado(item.estado)
  return (
    <div className="relative pt-2" data-testid="barra-proyeccion">
      <div className="h-2 rounded-full bg-line overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${animar ? usado : 0}%`, background: color }}
        />
      </div>
      {marcador !== null && item.proyectado > item.gastado && (
        <div
          className="absolute top-0 -translate-x-1/2 flex flex-col items-center pointer-events-none"
          style={{ left: `${marcador}%` }}
          data-testid="marcador-proyeccion"
          title={`Cierre estimado: ${Math.round(item.proyectado).toLocaleString('es-CO')}`}
        >
          <span
            className="block w-0 h-0"
            style={{
              borderLeft: '4px solid transparent',
              borderRight: '4px solid transparent',
              borderTop: `6px solid ${desborda ? 'var(--color-danger)' : 'var(--color-ink-soft)'}`,
            }}
          />
          <span className="block w-px h-3" style={{ background: desborda ? 'var(--color-danger)' : 'var(--color-ink-soft)' }} />
        </div>
      )}
    </div>
  )
}
