import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP, formatPorcentaje } from '../lib/format'
import Hoja from './Hoja'
import InputMonto from './InputMonto'

// Hoja inferior: cómo repartir un ingreso (gastos fijos, ahorro/metas, gasto libre
// y sobres). SOLO es una sugerencia: nada se mueve hasta que el usuario pulsa
// "Apartar para mis metas". `monto` llega precargado cuando viene de registrar un
// ingreso; si no, el usuario lo escribe.
export default function SugerenciaIngreso({ monto: montoInicial, cuentaId, onClose, onAplicado }) {
  const [monto, setMonto] = useState(montoInicial ? String(Math.round(montoInicial)) : '')
  const [sug, setSug] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [aplicando, setAplicando] = useState(false)
  const [error, setError] = useState('')

  async function calcular(valor = monto) {
    setError('')
    if (!valor || Number(valor) <= 0) return setError('Ingresa el monto del ingreso')
    setCargando(true)
    try {
      setSug(await api.distribuirIngreso(Number(valor)))
    } catch (err) {
      setError(err.message || 'No se pudo calcular la sugerencia. Revisa tu conexión e intenta de nuevo.')
    }
    setCargando(false)
  }

  useEffect(() => {
    if (montoInicial) calcular(String(Math.round(montoInicial)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const metas = sug?.metas?.filter((m) => m.monto > 0) || []

  async function aplicar() {
    setAplicando(true)
    setError('')
    try {
      for (const m of metas) {
        await api.aportarMeta(m.id, m.monto, cuentaId || undefined)
      }
      onAplicado?.()
      onClose()
    } catch (err) {
      setError(err.message || 'No se pudo apartar el dinero. Revisa tu conexión e intenta de nuevo.')
    }
    setAplicando(false)
  }

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-lg font-semibold">¿Cómo repartir este ingreso?</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>
      <p className="text-xs text-ink-soft mb-4">Es una sugerencia: tú decides si la sigues.</p>

      {!montoInicial && (
        <div className="flex gap-2 mb-4">
          <InputMonto entero
            value={monto}
            onValor={setMonto}
            placeholder="Monto del ingreso"
            className="flex-1 rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
          />
          <button onClick={() => calcular()} disabled={cargando} className="px-4 rounded-2xl bg-ink text-paper text-sm font-semibold disabled:opacity-60">
            Calcular
          </button>
        </div>
      )}

      {cargando && <p className="text-sm text-ink-soft text-center py-6">Calculando...</p>}

      {sug && !cargando && (
        <div data-testid="sugerencia-ingreso">
          <p className="text-sm mb-3">
            De <span className="font-bold">{formatCOP(sug.monto)}</span>, te sugiero:
          </p>
          <Fila etiqueta="Gastos fijos" detalle={formatPorcentaje((sug.necesidades / sug.monto) * 100, { decimales: 0 })} valor={sug.necesidades} />
          <Fila etiqueta="Ahorro" detalle={formatPorcentaje((sug.ahorro_total / sug.monto) * 100, { decimales: 0 })} valor={sug.ahorro_total} />
          {metas.map((m) => (
            <Fila key={m.id} etiqueta={`→ ${m.nombre}`} valor={m.monto} sub />
          ))}
          {sug.ahorro_libre > 0 && <Fila etiqueta="→ Ahorro libre" valor={sug.ahorro_libre} sub />}
          <Fila etiqueta="Gasto libre" detalle={formatPorcentaje((sug.gasto_libre / sug.monto) * 100, { decimales: 0 })} valor={sug.gasto_libre} />
          {sug.sobres.map((s) => (
            <Fila key={s.categoria} etiqueta={`→ Sobre ${s.categoria}`} valor={s.monto} sub />
          ))}
          {sug.avisos.map((a) => (
            <p key={a} className="text-xs text-danger mt-3">{a}</p>
          ))}
          <p className="text-[11px] text-ink-soft mt-3">
            Regla {Math.round(sug.regla.necesidades)}/{Math.round(sug.regla.deseos)}/{Math.round(sug.regla.ahorro)} — la puedes cambiar en Presupuesto → Ajustes.
          </p>
        </div>
      )}

      {error && <p className="text-sm text-danger mt-3" role="alert">{error}</p>}

      {sug && !cargando && (
        <div className="mt-4 space-y-2">
          {metas.length > 0 && (
            <button
              onClick={aplicar}
              disabled={aplicando}
              className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
            >
              {aplicando ? 'Apartando...' : 'Apartar para mis metas'}
            </button>
          )}
          {metas.length === 0 && (
            // Hoy la única acción que mueve dinero es apartar para metas (api.aportarMeta);
            // sin metas no hay nada que aplicar, así que se explica y se ofrece crear una.
            <p className="text-xs text-ink-soft text-center">
              Aún no tienes metas a las que apartar. <Link to="/metas" onClick={onClose} className="text-accent font-medium">Crear una meta</Link>
            </p>
          )}
          <button onClick={onClose} className="w-full text-sm text-ink-soft font-medium py-2">
            Ahora no
          </button>
        </div>
      )}
    </Hoja>
  )
}

function Fila({ etiqueta, detalle, valor, sub = false }) {
  return (
    <div className={`flex items-baseline justify-between py-1.5 ${sub ? 'pl-4 text-ink-soft text-xs' : 'text-sm border-t border-line first:border-t-0'}`}>
      <span className={sub ? '' : 'font-medium'}>
        {etiqueta} {detalle && <span className="text-ink-soft text-xs">({detalle})</span>}
      </span>
      <span className={sub ? '' : 'font-bold'}>{formatCOP(valor)}</span>
    </div>
  )
}
