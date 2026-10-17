import { useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { api } from '../lib/api'
import Hoja from './Hoja'

// Aviso discreto cuando el servidor devuelve `monedas_sin_tasa` no vacío: esas cuentas NO están sumadas en el
// total (el backend nunca mezcla monedas a ciegas). La acción lleva a poner la tasa a mano (PUT /perfil/tasas/X).
// Uso: <AvisoSinTasa monedas={datos?.monedas_sin_tasa} base={datos?.moneda_base} onResuelto={recargar} />

export function textoSinTasa(monedas) {
  const lista = (monedas || []).filter(Boolean)
  if (!lista.length) return ''
  if (lista.length === 1) return `No tenemos la tasa de ${lista[0]}: esas cuentas no están sumadas en el total.`
  const y = lista.length > 1 ? `${lista.slice(0, -1).join(', ')} y ${lista[lista.length - 1]}` : lista[0]
  return `No tenemos la tasa de ${y}: esas cuentas no están sumadas en el total.`
}

// «1 MXN = ___ COP». Acepta coma o punto decimal.
export function parsearTasa(texto) {
  const n = Number(String(texto ?? '').trim().replace(/\s/g, '').replace(',', '.'))
  return Number.isFinite(n) && n > 0 ? n : null
}

function HojaTasa({ monedas, base, onCerrar, onResuelto }) {
  const [valores, setValores] = useState({})
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function guardar(e) {
    e.preventDefault()
    const pendientes = monedas.filter((m) => String(valores[m] ?? '').trim() !== '')
    if (!pendientes.length) return setError('Escribe la tasa de al menos una moneda.')
    for (const m of pendientes) {
      if (!parsearTasa(valores[m])) return setError(`La tasa de ${m} debe ser un número mayor que cero.`)
    }
    setGuardando(true)
    setError('')
    try {
      for (const m of pendientes) await api.fijarTasaManual(m, parsearTasa(valores[m]))
      onResuelto?.()
      onCerrar()
    } catch (err) {
      setError(err.message || 'No pudimos guardar la tasa. Inténtalo de nuevo.')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onCerrar} titulo="Poner la tasa" testId="hoja-tasa">
      <form onSubmit={guardar} className="space-y-4">
        <p className="text-sm text-ink-soft">
          Cuántas {base} vale 1 de cada moneda. Solo la usamos en tus totales; puedes cambiarla cuando quieras.
        </p>
        {monedas.map((m) => (
          <label key={m} className="block text-sm">
            <span className="block mb-1">1 {m} =</span>
            <div className="flex items-center gap-2">
              <input
                inputMode="decimal"
                value={valores[m] ?? ''}
                onChange={(e) => setValores((v) => ({ ...v, [m]: e.target.value }))}
                aria-label={`Tasa de ${m} en ${base}`}
                className="flex-1 min-h-11 rounded-xl border border-line bg-paper-raised px-3"
              />
              <span className="text-ink-soft">{base}</span>
            </div>
          </label>
        ))}
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <button type="submit" disabled={guardando} className="w-full min-h-11 rounded-xl bg-accent text-paper-raised font-semibold">
          {guardando ? 'Guardando…' : 'Guardar tasa'}
        </button>
      </form>
    </Hoja>
  )
}

export default function AvisoSinTasa({ monedas, base = 'COP', onResuelto, className = '' }) {
  const [abierta, setAbierta] = useState(false)
  const lista = (monedas || []).filter(Boolean)
  if (!lista.length) return null
  return (
    <>
      <div role="status" className={`flex items-start gap-2 rounded-xl border border-line bg-paper-raised px-3 py-2 text-xs text-ink-soft ${className}`}>
        <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
        <p className="flex-1">
          {textoSinTasa(lista)}{' '}
          <button type="button" onClick={() => setAbierta(true)} className="font-semibold text-accent underline min-h-11 px-1">
            Poner tasa
          </button>
        </p>
      </div>
      {abierta && <HojaTasa monedas={lista} base={base} onCerrar={() => setAbierta(false)} onResuelto={onResuelto} />}
    </>
  )
}
