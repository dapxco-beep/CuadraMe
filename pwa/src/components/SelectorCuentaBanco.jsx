import { CreditCard } from 'lucide-react'
import { recordarCuenta, textoOpcionCuenta } from '../lib/cuentasBanco'

/**
 * Selector de cuenta para correos / extractos. Si el banco tiene varias cuentas
 * (ahorros y tarjeta), cada opción dice «Débito/Ahorros» o «Tarjeta de crédito»; y si
 * el servidor no pudo decidir (`pregunta`), lo dice en lenguaje simple en vez de adivinar.
 * Al elegir, recuerda la cuenta para ese banco + tipo (`banco`, `producto`).
 */
export default function SelectorCuentaBanco({
  cuentas, value, onChange, ariaLabel, vacio = 'Elige la cuenta', banco, producto, pregunta, sugeridaId, candidatas, className = '',
}) {
  // Las candidatas van primero, pero no se esconde ninguna cuenta: la persona manda.
  const lista = candidatas?.length > 1
    ? [...cuentas.filter((c) => candidatas.includes(c.id)), ...cuentas.filter((c) => !candidatas.includes(c.id))]
    : cuentas
  const preguntar = !!pregunta && !value
  return (
    <div className={className}>
      {preguntar && (
        <p className="flex items-start gap-1.5 text-xs font-medium text-accent mb-1.5" data-testid="pregunta-cuenta">
          <CreditCard size={16} className="shrink-0" aria-hidden="true" />
          <span>{pregunta} Elige cuál para seguir.</span>
        </p>
      )}
      <select
        value={value}
        onChange={(e) => {
          recordarCuenta(banco, producto, e.target.value)
          onChange(e.target.value)
        }}
        aria-label={ariaLabel}
        className="w-full rounded-xl border border-line bg-paper-raised px-3 py-2 text-xs"
      >
        <option value="">{vacio}</option>
        {lista.map((c) => (
          <option key={c.id} value={c.id}>
            {textoOpcionCuenta(c, cuentas)}{c.id === sugeridaId ? ' (sugerida)' : ''}
          </option>
        ))}
      </select>
    </div>
  )
}
