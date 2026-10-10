import { useCallback, useEffect, useState } from 'react'
import { Plus, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { calcularCuota, mesAnio } from '../lib/cuotas'
import { leerMonto } from '../lib/cuentaNueva'
import Hoja from './Hoja'
import InputMonto from './InputMonto'

const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
function fechaCorta(iso) {
  if (!iso) return ''
  const [, m, d] = iso.split('-')
  return `${parseInt(d, 10)} ${MESES_CORTOS[parseInt(m, 10) - 1]}`
}

// Compras a cuotas de una tarjeta. Es una VISTA de compromiso: la compra original ya
// bajó el saldo de la tarjeta por el total, así que aquí nada mueve el saldo.
export default function ComprasACuotas({ cuenta }) {
  const [datos, setDatos] = useState({ comprometido_mes: 0, planes: [] })
  const [agregando, setAgregando] = useState(false)
  const [quitando, setQuitando] = useState(null)
  const [error, setError] = useState('')

  const cargar = useCallback(async () => {
    try {
      const r = await api.cuotasTarjeta(cuenta.id)
      if (r && Array.isArray(r.planes)) setDatos(r)
    } catch {
      // sin conexión o sin la función: la sección queda vacía, no rompe la tarjeta
    }
  }, [cuenta.id])

  useEffect(() => {
    cargar()
  }, [cargar])

  const vigentes = datos.planes.filter((p) => !p.terminado)

  async function marcarPagada(id) {
    setError('')
    try {
      await api.pagarCuotaTarjeta(id)
      await cargar()
    } catch (err) {
      setError(err.message || 'No se pudo marcar la cuota')
    }
  }

  async function quitar(id) {
    setError('')
    try {
      await api.eliminarCuotaTarjeta(id)
      setQuitando(null)
      await cargar()
    } catch (err) {
      setError(err.message || 'No se pudo quitar')
    }
  }

  return (
    <section className="mt-3 rounded-xl border border-line bg-paper p-3 text-xs" aria-label="Compras a cuotas" data-testid="compras-cuotas">
      <h3 className="font-semibold text-sm">Compras a cuotas</h3>

      {vigentes.length > 0 && (
        <p className="mt-1" data-testid="comprometido-cuotas">
          <span className="text-ink-soft">Comprometido en cuotas este mes: </span>
          <span className="font-semibold">{formatMoneda(datos.comprometido_mes, cuenta.moneda)}</span>
        </p>
      )}

      {vigentes.length === 0 ? (
        <p className="text-ink-soft mt-1">Si compraste algo diferido a varias cuotas, agrégalo para ver cuánto te toca pagar cada mes.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {vigentes.map((p) => (
            <li key={p.id} className="rounded-lg bg-paper-raised border border-line p-2.5" data-testid="plan-cuotas">
              <div className="flex justify-between gap-2">
                <span className="font-semibold">{p.descripcion}</span>
                <span className="font-semibold shrink-0">{formatMoneda(p.cuota_mensual, cuenta.moneda)}/mes</span>
              </div>
              <p className="text-ink-soft mt-0.5">
                Va en {p.numero_actual} de {p.num_cuotas} · Saldo pendiente {formatMoneda(p.saldo_pendiente, cuenta.moneda)} · Termina en {mesAnio(p.termina_en)}
              </p>
              <div className="flex gap-3 mt-1.5">
                <button onClick={() => marcarPagada(p.id)} className="text-accent font-medium min-h-[32px]">
                  Marcar cuota pagada
                </button>
                {quitando === p.id ? (
                  <span className="flex items-center gap-2">
                    <span className="text-ink-soft">¿Quitar? El saldo no cambia.</span>
                    <button onClick={() => quitar(p.id)} className="text-danger font-medium min-h-[32px]">Sí</button>
                    <button onClick={() => setQuitando(null)} className="text-ink-soft min-h-[32px]">No</button>
                  </span>
                ) : (
                  <button onClick={() => setQuitando(p.id)} className="text-ink-soft min-h-[32px]" aria-label={`Quitar ${p.descripcion}`}>
                    Quitar
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {error && <p role="alert" className="text-danger mt-2">{error}</p>}

      <button onClick={() => setAgregando(true)} className="mt-2 flex items-center gap-1.5 text-sm text-accent font-medium min-h-[44px]">
        <Plus size={16} /> Agregar compra a cuotas
      </button>

      {agregando && (
        <FormCuotas
          cuenta={cuenta}
          onClose={() => setAgregando(false)}
          onGuardada={async () => {
            setAgregando(false)
            await cargar()
          }}
        />
      )}
    </section>
  )
}

function FormCuotas({ cuenta, onClose, onGuardada }) {
  const [descripcion, setDescripcion] = useState('')
  const [monto, setMonto] = useState('')
  const [cuotas, setCuotas] = useState('')
  const [tasa, setTasa] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const total = leerMonto(monto)
  const n = Number(cuotas)
  const cuota = calcularCuota(total, n, Number(tasa) || 0)
  const campo = 'w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mt-1'

  async function guardar() {
    setError('')
    if (!descripcion.trim()) return setError('Cuéntanos qué compraste')
    if (!(total > 0)) return setError('Escribe el valor de la compra')
    if (!(n >= 1 && n <= 120)) return setError('Las cuotas deben ser entre 1 y 120')
    if (tasa !== '' && (Number(tasa) < 0 || Number(tasa) > 20)) return setError('La tasa mensual debe estar entre 0 y 20%')
    setGuardando(true)
    try {
      await api.crearCuotaTarjeta({
        cuenta_id: cuenta.id, descripcion: descripcion.trim(), total, num_cuotas: n, tasa_mensual: Number(tasa) || 0,
      })
      await onGuardada()
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onClose} ariaLabel="Agregar compra a cuotas">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Compra a cuotas</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>
      <label className="block mb-3">
        <span className="text-xs text-ink-soft">¿Qué compraste?</span>
        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Ej. Nevera" aria-label="Qué compraste" className={campo} />
      </label>
      <label className="block mb-3">
        <span className="text-xs text-ink-soft">Valor de la compra</span>
        <InputMonto
          value={monto}
          onValor={setMonto}
          placeholder="Ej. 1.200.000"
          aria-label="Valor de la compra"
          className={campo}
        />
      </label>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <label className="block">
          <span className="text-xs text-ink-soft">Número de cuotas</span>
          <input
            value={cuotas}
            onChange={(e) => setCuotas(e.target.value.replace(/\D/g, '').slice(0, 3))}
            inputMode="numeric"
            placeholder="Ej. 12"
            aria-label="Número de cuotas"
            className={campo}
          />
        </label>
        <label className="block">
          <span className="text-xs text-ink-soft">Tasa mensual % (opcional)</span>
          <input
            value={tasa}
            onChange={(e) => setTasa(e.target.value.replace(/[^\d.]/g, ''))}
            inputMode="decimal"
            placeholder="0 = sin interés"
            aria-label="Tasa mensual"
            className={campo}
          />
        </label>
      </div>
      {cuota > 0 && (
        <p className="rounded-xl bg-paper-raised border border-line p-3 text-sm mb-3" data-testid="vista-cuota">
          Cuota mensual: <span className="font-semibold">{formatMoneda(cuota, cuenta.moneda)}</span>
          {cuenta.tarjeta?.proximo_corte && (
            <span className="block text-xs text-ink-soft mt-1">
              La primera cuota cae en tu próximo corte ({fechaCorta(cuenta.tarjeta.proximo_corte)}).
            </span>
          )}
        </p>
      )}
      <p className="text-xs text-ink-soft mb-4">
        Esto no cambia el saldo de tu tarjeta: la compra ya está registrada. Solo te mostramos cuánto te toca pagar cada mes.
      </p>
      {error && <p role="alert" className="text-sm text-danger mb-3">{error}</p>}
      <button onClick={guardar} disabled={guardando} className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60">
        {guardando ? 'Guardando...' : 'Guardar'}
      </button>
    </Hoja>
  )
}
