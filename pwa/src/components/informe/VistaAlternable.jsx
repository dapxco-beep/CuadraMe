/**
 * Un solo panel con dos formas de ver lo mismo (p. ej. «Tabla | Gráfica»). Así no hay dos tarjetas con los mismos datos.
 * `opciones`: [{ id, texto, nodo }]. Controlado: `valor` y `onCambio`.
 */
export default function VistaAlternable({ etiqueta, opciones, valor, onCambio, className = '' }) {
  const activa = opciones.find((o) => o.id === valor) || opciones[0]
  return (
    <div className={className}>
      <div role="group" aria-label={etiqueta} className="flex justify-end mb-2">
        <div className="flex rounded-full bg-paper-raised border border-line p-0.5">
          {opciones.map((o) => (
            <button
              key={o.id}
              type="button"
              aria-pressed={o.id === activa.id}
              onClick={() => onCambio(o.id)}
              data-testid={`vista-${o.id}`}
              className={`px-3.5 min-h-11 rounded-full text-xs font-semibold ${o.id === activa.id ? 'bg-accent text-paper-raised' : 'text-ink-soft'}`}
            >
              {o.texto}
            </button>
          ))}
        </div>
      </div>
      {activa.nodo}
    </div>
  )
}
