// Sistema único de gráficas de CuadraMe.
//
// Decisiones clave (para que todas se vean y se lean igual):
//  - Colores SOLO desde los tokens del tema (var(--color-*)), así funcionan en claro y oscuro.
//  - Dibujamos con HTML/CSS (barras con alto en %) en vez de SVG estirado: el texto no se deforma.
//  - Cada gráfica trae un resumen en texto (sr-only) y aria-label, para lectores de pantalla
//    y para que nadie dependa solo del color.
//  - Un solo tooltip (TooltipGrafico) y un solo estado vacío (GraficoVacio).
import { useId, useState } from 'react'
import { formatCOP } from '../../lib/format'

export const COLORES = {
  ingreso: 'var(--color-accent-2)',
  gasto: 'var(--color-ink)',
  principal: 'var(--color-accent)',
  alerta: 'var(--color-accent-2)',
  peligro: 'var(--color-danger)',
  pista: 'var(--color-line)',
}

// Color de una barra de avance según qué tan cerca está del límite.
export function colorAvance(pct, alerta = 80) {
  if (pct > 100) return COLORES.peligro
  if (pct >= alerta) return COLORES.alerta
  return COLORES.principal
}

export function TooltipGrafico({ titulo, lineas = [], className = '' }) {
  return (
    <div
      role="status"
      className={`bg-ink text-paper text-xs rounded-xl px-3 py-2 shadow-lg pointer-events-none whitespace-nowrap ${className}`}
    >
      {titulo && <p className="font-semibold">{titulo}</p>}
      {lineas.map((l) => (
        <p key={l}>{l}</p>
      ))}
    </div>
  )
}

export function GraficoVacio({ mensaje = 'Aún no hay datos para mostrar esta gráfica', alto = 96 }) {
  return (
    <div
      className="rounded-2xl border border-dashed border-line text-center flex items-center justify-center px-4"
      style={{ minHeight: alto }}
    >
      <p className="text-xs text-ink-soft">{mensaje}</p>
    </div>
  )
}

export function Leyenda({ series }) {
  return (
    <div className="flex items-center gap-4 mt-2 justify-center flex-wrap">
      {series.map((s) => (
        <span key={s.nombre} className="flex items-center gap-1.5 text-xs text-ink-soft">
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: s.color }} aria-hidden="true" /> {s.nombre}
        </span>
      ))}
    </div>
  )
}

/**
 * Barras agrupadas. datos: [{ clave, etiqueta, valores: [n, n] }], series: [{ nombre, color }]
 * Se puede recorrer con teclado (Tab) y con el dedo; el tooltip aparece en ambos casos.
 */
export function GraficoBarras({ datos, series, titulo, formato = formatCOP, alto = 150, vacio }) {
  const [activo, setActivo] = useState(null)
  const idResumen = useId()

  const hayDatos = datos.some((d) => d.valores.some((v) => v > 0))
  if (!datos.length || !hayDatos) return <GraficoVacio mensaje={vacio} />

  const maximo = Math.max(1, ...datos.flatMap((d) => d.valores))
  const texto = (d) => series.map((s, j) => `${s.nombre.toLowerCase()} ${formato(d.valores[j])}`).join(', ')
  const resumen = datos.map((d) => `${d.etiqueta}: ${texto(d)}`).join('. ')

  return (
    <div>
      <div role="group" aria-label={titulo} aria-describedby={idResumen}>
        <p id={idResumen} className="sr-only">{resumen}</p>
        <div className="flex items-end gap-1.5 border-b border-line" style={{ height: alto }}>
          {datos.map((d, i) => {
            const enfocado = activo === i
            return (
              <div key={d.clave} className="relative flex-1 h-full flex items-end justify-center">
                <button
                  type="button"
                  aria-label={`${d.etiqueta}: ${texto(d)}`}
                  className="w-full h-full flex items-end justify-center gap-[3px] rounded-md"
                  style={{ opacity: activo === null || enfocado ? 1 : 0.4 }}
                  onMouseEnter={() => setActivo(i)}
                  onMouseLeave={() => setActivo(null)}
                  onFocus={() => setActivo(i)}
                  onBlur={() => setActivo(null)}
                  onTouchStart={() => setActivo(i)}
                >
                  {series.map((s, j) => (
                    <span
                      key={s.nombre}
                      className="w-[38%] max-w-[18px] rounded-t-md"
                      style={{ height: `${(d.valores[j] / maximo) * 100}%`, minHeight: d.valores[j] > 0 ? 2 : 0, background: s.color }}
                    />
                  ))}
                </button>
                {enfocado && (
                  <div className="absolute bottom-full mb-1 z-10 left-1/2 -translate-x-1/2">
                    <TooltipGrafico titulo={d.etiqueta} lineas={series.map((s, j) => `${s.nombre} ${formato(d.valores[j])}`)} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
        <div className="flex gap-1.5 mt-1.5" aria-hidden="true">
          {datos.map((d) => (
            <span key={d.clave} className="flex-1 text-center text-[11px] text-ink-soft">{d.etiqueta}</span>
          ))}
        </div>
      </div>
      <Leyenda series={series} />
    </div>
  )
}

/** Línea mínima de tendencia (sin ejes). valores: números en orden cronológico. */
export function Sparkline({ valores, etiqueta, color = COLORES.principal, formato = formatCOP, ancho = 120, alto = 32 }) {
  if (!valores || valores.length < 2) return null
  const min = Math.min(...valores)
  const max = Math.max(...valores)
  const rango = max - min || 1
  const puntos = valores.map((v, i) => [(i / (valores.length - 1)) * ancho, alto - 3 - ((v - min) / rango) * (alto - 6)])
  const linea = puntos.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const inicio = valores[0]
  const fin = valores[valores.length - 1]
  const sentido = fin > inicio ? 'sube' : fin < inicio ? 'baja' : 'se mantiene'
  const resumen = `${etiqueta}: ${sentido}, de ${formato(inicio)} a ${formato(fin)}`

  return (
    <svg viewBox={`0 0 ${ancho} ${alto}`} role="img" aria-label={resumen} className="w-full" style={{ height: alto }} preserveAspectRatio="none">
      <title>{resumen}</title>
      <polyline points={linea} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

/** Barra de avance (horizontal) o termómetro (vertical). pct: 0 a 100. */
export function BarraProgreso({ pct, etiqueta, color = COLORES.principal, vertical = false, alto, animar = true, grosor = 8 }) {
  const valor = Math.max(0, Math.min(100, Math.round(pct)))
  const relleno = animar ? valor : 0
  const aria = { role: 'progressbar', 'aria-label': etiqueta, 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': valor, 'aria-valuetext': `${valor}%` }
  if (vertical) {
    return (
      <div {...aria} className="w-8 rounded-full overflow-hidden relative" style={{ height: alto, background: COLORES.pista }}>
        <div className="absolute bottom-0 left-0 right-0 rounded-full transition-all duration-700 ease-out" style={{ height: `${relleno}%`, background: color }} />
      </div>
    )
  }
  return (
    <div {...aria} className="rounded-full overflow-hidden" style={{ height: grosor, background: COLORES.pista }}>
      <div className="h-full rounded-full transition-all duration-700 ease-out" style={{ width: `${relleno}%`, background: color }} />
    </div>
  )
}

/** Cuadrícula de intensidad (7 columnas). celdas: [{ clave, nivel, texto }], niveles: colores de menos a más. */
export function MapaCalor({ celdas, titulo, niveles }) {
  if (!celdas.length) return <GraficoVacio />
  const conGasto = celdas.filter((c) => c.nivel > 0).length
  return (
    <div>
      <p className="sr-only">{`${titulo}: ${conGasto} de ${celdas.length} días con gasto`}</p>
      <div role="group" aria-label={titulo} className="grid grid-cols-7 gap-1.5">
        {celdas.map((c, i) => (
          <div
            key={c.clave}
            role="img"
            aria-label={c.texto}
            title={c.texto}
            className="aspect-square rounded-[6px] pop-in"
            style={{ background: niveles[c.nivel], animationDelay: `${Math.min(i, 20) * 12}ms` }}
          />
        ))}
      </div>
      <div className="flex items-center gap-1.5 mt-2.5 text-[11px] text-ink-soft" aria-hidden="true">
        <span>Menos</span>
        {niveles.map((fondo, i) => (
          <span key={i} className="w-2.5 h-2.5 rounded-[3px]" style={{ background: fondo }} />
        ))}
        <span>Más</span>
      </div>
    </div>
  )
}
