// Barra de progreso accesible. Anima con transform: scaleX (compuesto en la GPU) en vez de
// `width`, que obliga al navegador a recalcular el layout en cada fotograma.
// Con "reducir movimiento" la transición se anula (ver .barra-fill en index.css).
export default function BarraProgreso({
  pct = 0,
  color,
  label,
  texto,
  className = 'h-2 rounded-full bg-line overflow-hidden',
  fillClass = 'rounded-full',
  vertical = false,
  style,
}) {
  const p = Math.max(0, Math.min(100, Number.isFinite(pct) ? pct : 0))
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(p)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuetext={texto}
      aria-label={label}
      className={className}
      style={style}
    >
      <div
        className={`${vertical ? 'barra-fill-v' : 'barra-fill'} w-full h-full ${color ? '' : 'bg-accent'} ${fillClass}`}
        style={{ transform: vertical ? `scaleY(${p / 100})` : `scaleX(${p / 100})`, ...(color ? { background: color } : {}) }}
      />
    </div>
  )
}
