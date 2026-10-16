// Lectura flotante de un gráfico (tooltip): título + filas «etiqueta · valor». Se coloca sobre la columna
// activa sin salirse del recuadro (a la izquierda, centrada o a la derecha según dónde esté).
// Es solo visual: el mismo contenido llega a lectores de pantalla por la región aria-live del gráfico.
export default function Lectura({ pct, titulo, filas = [], pie = null }) {
  const pos = pct < 28 ? 'translateX(-14%)' : pct > 72 ? 'translateX(-86%)' : 'translateX(-50%)'
  return (
    <div
      data-testid="lectura"
      aria-hidden="true"
      className="absolute top-0 z-10 pointer-events-none rounded-xl border border-line bg-paper-raised/95 backdrop-blur px-3 py-2 shadow-lg min-w-[148px] max-w-[220px]"
      style={{ left: `${pct}%`, transform: pos }}
    >
      <p className="text-[11px] font-semibold text-ink first-letter:uppercase leading-tight">{titulo}</p>
      <dl className="mt-1 space-y-0.5">
        {filas.map((f) => (
          <div key={f.nombre} className="flex items-center justify-between gap-3 text-[11px] leading-snug">
            <dt className="flex items-center gap-1.5 text-ink-soft min-w-0">
              {f.color && <span className="w-2 h-2 rounded-full shrink-0" style={{ background: f.color }} />}
              <span className="truncate">{f.nombre}</span>
            </dt>
            <dd className={`font-semibold t-cifra shrink-0 ${f.clase || 'text-ink'}`}>{f.valor}</dd>
          </div>
        ))}
      </dl>
      {pie && <p className="text-[10px] text-ink-soft mt-1 leading-snug">{String(pie).replace(/ %/g, ' %')}</p>}
    </div>
  )
}
