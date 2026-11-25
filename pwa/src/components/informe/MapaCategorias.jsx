// Mapa de categorías (treemap): cada rectángulo es una categoría y su área es lo que gastaste en ella. De un vistazo se ve
// qué pesa más. Reparto simple: se parte la lista en dos mitades de peso parecido, alternando corte vertical y horizontal.
const COLORES = [1, 2, 3, 4, 5, 6].map((n) => `var(--c-serie-${n})`)

export function repartirMapa(items, x = 0, y = 0, w = 100, h = 100, salida = []) {
  if (!items.length) return salida
  if (items.length === 1) {
    salida.push({ ...items[0], x, y, w, h })
    return salida
  }
  const total = items.reduce((s, i) => s + i.v, 0)
  let acc = 0
  let k = 0
  while (k < items.length - 1 && acc + items[k].v <= total / 2) acc += items[k++].v
  if (k === 0) acc = items[k++].v
  const izq = items.slice(0, k)
  const der = items.slice(k)
  const f = total ? acc / total : 0.5
  if (w >= h) {
    repartirMapa(izq, x, y, w * f, h, salida)
    repartirMapa(der, x + w * f, y, w * (1 - f), h, salida)
  } else {
    repartirMapa(izq, x, y, w, h * f, salida)
    repartirMapa(der, x, y + h * f, w, h * (1 - f), salida)
  }
  return salida
}

export default function MapaCategorias({ segmentos, fmt, iconoDe, alto = 240 }) {
  const items = segmentos.map((s, i) => ({ ...s, v: Math.max(s.monto, 1), color: COLORES[i % COLORES.length] }))
  const rects = repartirMapa(items)
  const resumen = `Mapa del gasto por categoría: ${segmentos.map((s) => `${s.nombre} ${String(s.pct).replace('.', ',')} %`).join(', ')}.`
  return (
    <div className="relative w-full rounded-2xl overflow-hidden" style={{ height: alto }} role="img" aria-label={resumen} data-testid="mapa-categorias">
      {rects.map((r) => {
        const area = (r.w * r.h) / 100 // % del total
        return (
          <div
            key={r.nombre}
            aria-hidden="true"
            className="absolute p-0.5"
            style={{ left: `${r.x}%`, top: `${r.y}%`, width: `${r.w}%`, height: `${r.h}%` }}
          >
            <div
              className="h-full w-full rounded-xl px-2 py-1.5 overflow-hidden flex flex-col justify-between"
              style={{ background: `color-mix(in srgb, ${r.color} 24%, var(--color-paper-raised))`, borderLeft: `4px solid ${r.color}` }}
            >
              {area >= 4 && (
                <p className="text-[11px] font-semibold leading-tight text-ink break-words">
                  {area >= 8 && iconoDe && <span className="mr-1">{iconoDe(r.nombre)}</span>}
                  {r.nombre}
                </p>
              )}
              {area >= 7 && (
                <p className="text-[11px] leading-tight text-ink-soft">
                  {String(r.pct).replace('.', ',')} %{area >= 14 && <span className="block font-semibold text-ink">{fmt(r.monto)}</span>}
                </p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
