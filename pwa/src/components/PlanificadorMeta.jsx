import { useState } from 'react'
import { X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'

// 'YYYY-MM' -> último día de ese mes a mediodía (ISO local), p. ej. '2027-12' -> '2027-12-31T12:00:00'
export function finDeMes(ym) {
  const [y, m] = String(ym).split('-').map(Number)
  const ultimo = new Date(Date.UTC(y, m, 0)).getUTCDate()
  return `${y}-${String(m).padStart(2, '0')}-${String(ultimo).padStart(2, '0')}T12:00:00`
}

const COLOR_VIABILIDAD = {
  lograda: 'text-accent',
  viable: 'text-accent',
  ajustada: 'text-accent-2',
  incompatible: 'text-danger',
  fecha_vencida: 'text-danger',
  sin_datos: 'text-ink-soft',
}
const TEXTO_VIABILIDAD = {
  lograda: 'Ya la lograste',
  viable: 'Va bien con tus números',
  ajustada: 'Posible, pero ajustada',
  incompatible: 'No cuadra con tus ingresos y gastos',
  fecha_vencida: 'La fecha ya pasó',
  sin_datos: 'Aún no tengo suficientes datos tuyos',
}

// "Quiero $12 millones en diciembre de 2027" -> cuánto aportar al mes, si es
// compatible con lo que realmente ahorra y en cuántos meses la logra a su ritmo.
export default function PlanificadorMeta({ onClose, onCreada }) {
  const [objetivo, setObjetivo] = useState('')
  const [mes, setMes] = useState('')
  const [saldo, setSaldo] = useState('')
  const [tasa, setTasa] = useState('')
  const [nombre, setNombre] = useState('')
  const [plan, setPlan] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')

  async function calcular() {
    setError('')
    if (!objetivo || Number(objetivo) <= 0) return setError('¿Cuánto quieres reunir?')
    if (!mes) return setError('Elige el mes en que la quieres lograr')
    setCargando(true)
    try {
      setPlan(
        await api.planMeta({
          objetivo: Number(objetivo),
          fecha_objetivo: finDeMes(mes),
          saldo_actual: Number(saldo) || 0,
          tasa_ea: Number(tasa) || 0,
        })
      )
    } catch (err) {
      setError(err.message || 'No se pudo calcular')
    }
    setCargando(false)
  }

  async function crear() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a tu meta')
    try {
      await api.crearMeta({
        nombre: nombre.trim(),
        monto_objetivo: Number(objetivo),
        monto_actual: Number(saldo) || 0,
        fecha_objetivo: finDeMes(mes),
      })
      onCreada()
    } catch (err) {
      setError(err.message || 'No se pudo crear la meta')
    }
  }

  const campo = 'w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3'

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50 sheet-backdrop">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8 max-h-[90vh] overflow-y-auto sheet-content">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold">Planear una meta</h2>
          <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>
        <p className="text-xs text-ink-soft mb-4">Dime cuánto y para cuándo; yo calculo cuánto aportar según lo que de verdad ahorras.</p>

        <input value={objetivo} onChange={(e) => setObjetivo(e.target.value.replace(/\D/g, ''))} inputMode="numeric"
          placeholder="¿Cuánto quieres reunir? (ej. 12000000)" aria-label="Monto que quieres reunir" className={campo} />
        <label className="text-xs text-ink-soft">¿Para qué mes?</label>
        <input type="month" value={mes} onChange={(e) => setMes(e.target.value)} aria-label="Mes objetivo" className={`${campo} mt-1`} />
        <input value={saldo} onChange={(e) => setSaldo(e.target.value.replace(/\D/g, ''))} inputMode="numeric"
          placeholder="Lo que ya tienes para esta meta (opcional)" aria-label="Saldo actual" className={campo} />
        <input value={tasa} onChange={(e) => setTasa(e.target.value.replace(/[^\d.]/g, ''))} inputMode="decimal"
          placeholder="Rendimiento % E.A. si lo inviertes (opcional)" aria-label="Rendimiento EA" className={campo} />

        {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}
        <button onClick={calcular} disabled={cargando} className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60">
          {cargando ? 'Calculando...' : 'Calcular mi plan'}
        </button>

        {plan && (
          <div className="mt-5 rounded-2xl bg-paper-raised border border-line p-4" data-testid="plan-meta">
            <p className={`text-sm font-semibold ${COLOR_VIABILIDAD[plan.viabilidad] || ''}`}>
              {TEXTO_VIABILIDAD[plan.viabilidad] || ''}
            </p>
            {plan.aporte_requerido != null && plan.viabilidad !== 'lograda' && (
              <p className="text-2xl font-bold mt-1">
                {formatCOP(plan.aporte_requerido)} <span className="text-sm font-medium text-ink-soft">al mes</span>
              </p>
            )}
            {plan.advertencia && <p className="text-xs text-danger mt-2">{plan.advertencia}</p>}
            {plan.mensaje && <p className="text-xs text-ink-soft mt-2">{plan.mensaje}</p>}
            {plan.capacidad_ahorro != null && (
              <p className="text-[11px] text-ink-soft mt-2">
                Según tus últimos meses te sobran unos {formatCOP(plan.capacidad_ahorro)} al mes.
              </p>
            )}

            <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre de la meta (ej. Viaje a Japón)"
              aria-label="Nombre de la meta" className={`${campo} mt-4 mb-2`} />
            <button onClick={crear} className="w-full border border-accent text-accent font-semibold rounded-2xl py-3 text-sm">
              Crear esta meta
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
