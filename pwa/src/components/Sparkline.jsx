import { useId } from 'react'

// Mini gráfica de tendencia (sparkline). Accesible: el SVG es una imagen con nombre y el
// mismo resumen queda disponible como texto (`resumen`), para que no dependa de la vista.
// Hereda el color del texto (currentColor), así sirve sobre el héroe oscuro y sobre papel.
// Con menos de 2 puntos no dibuja nada (no hay tendencia que mostrar).
export default function Sparkline({ valores = [], resumen, ancho = 120, alto = 36, className = '' }) {
  const id = useId()
  const datos = valores.filter((v) => Number.isFinite(v))
  if (datos.length < 2) return null
  const min = Math.min(...datos)
  const max = Math.max(...datos)
  const rango = max - min || 1
  const pad = 3
  const x = (i) => pad + (i * (ancho - pad * 2)) / (datos.length - 1)
  const y = (v) => alto - pad - ((v - min) / rango) * (alto - pad * 2)
  const linea = datos.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')
  const area = `${linea} L${x(datos.length - 1).toFixed(1)} ${alto} L${x(0).toFixed(1)} ${alto} Z`
  const ultimo = datos.length - 1
  return (
    <svg
      role="img"
      aria-label={resumen}
      viewBox={`0 0 ${ancho} ${alto}`}
      width={ancho}
      height={alto}
      className={className}
      data-testid="sparkline"
    >
      <title>{resumen}</title>
      <defs>
        <linearGradient id={`${id}-g`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.28" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id}-g)`} />
      <path d={linea} fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={x(ultimo)} cy={y(datos[ultimo])} r="2.5" fill="currentColor" />
    </svg>
  )
}

// Texto de resumen en español: «Gasto de los últimos 6 meses: de $X a $Y (sube 12 %)»
export function resumenTendencia(valores, formato, etiqueta = 'Gasto mensual') {
  const datos = valores.filter((v) => Number.isFinite(v))
  if (datos.length < 2) return ''
  const primero = datos[0]
  const ultimo = datos[datos.length - 1]
  let cambio = 'se mantiene igual'
  if (primero > 0) {
    const pct = Math.round(((ultimo - primero) / primero) * 100)
    cambio = pct === 0 ? 'se mantiene igual' : `${pct > 0 ? 'sube' : 'baja'} ${Math.abs(pct)} %`
  } else if (ultimo > 0) {
    cambio = 'sube'
  }
  return `${etiqueta}, últimos ${datos.length} meses: de ${formato(primero)} a ${formato(ultimo)} (${cambio})`
}
