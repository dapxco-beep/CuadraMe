import { claveComercio, huellaPeligrosa } from '../lib/comercio'

// Estado inicial al editar la categoría de una fila: "Recordar" va MARCADO por defecto.
export const RECORDAR_INICIAL = { recordar: true, anteriores: false }

/**
 * Casillas "Recordar para «vento coliving»" y "Aplicar también a los anteriores",
 * que aparecen bajo la fila cuyo usuario cambió la categoría. Así el sistema aprende:
 * la próxima vez que salga ese comercio ya sabrá qué es.
 * Si la huella es demasiado genérica (p. ej. «d1» o «pago») no se guarda sin que el
 * usuario lo confirme desde "Entrenar categorías", y aquí se le avisa.
 */
export default function RecordarRegla({ descripcion, valor, onChange, className = '' }) {
  const huella = claveComercio(descripcion)
  const peligro = huellaPeligrosa(huella)
  const v = valor || RECORDAR_INICIAL
  if (!huella && !peligro) return null
  return (
    <div className={`text-xs ${className}`} data-testid="recordar-regla">
      {peligro ? (
        <p className="text-ink-soft">No guardo una regla para esta fila: {peligro.charAt(0).toLowerCase() + peligro.slice(1)}.</p>
      ) : (
        <>
          <label className="flex items-center gap-2 text-ink">
            <input
              type="checkbox"
              checked={!!v.recordar}
              onChange={(e) => onChange({ ...v, recordar: e.target.checked, anteriores: e.target.checked ? v.anteriores : false })}
              className="w-4 h-4 accent-accent shrink-0"
            />
            <span>
              Recordar para «<b>{huella}</b>»
            </span>
          </label>
          {v.recordar && (
            <label className="flex items-center gap-2 text-ink-soft mt-1.5 ml-6">
              <input
                type="checkbox"
                checked={!!v.anteriores}
                onChange={(e) => onChange({ ...v, anteriores: e.target.checked })}
                className="w-4 h-4 accent-accent shrink-0"
              />
              <span>Aplicar también a los anteriores</span>
            </label>
          )}
        </>
      )}
    </div>
  )
}
