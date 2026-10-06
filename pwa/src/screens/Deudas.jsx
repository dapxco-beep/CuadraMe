import { useEffect, useState } from 'react'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Plus, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { ENTIDADES_FINANCIERAS_CO } from '../lib/entidadesFinancierasCO'
import SimuladorDeudas from '../components/SimuladorDeudas'

const urgenciaColor = {
  critico: 'text-danger',
  proximo: 'text-accent-2',
  normal: 'text-ink-soft',
}

export default function Deudas() {
  const volver = useVolver('/perfil')
  const { recargar: recargarCuentas } = useCuentas()
  const [deudas, setDeudas] = useState([])
  const [cargando, setCargando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [pagando, setPagando] = useState(null)
  const [error, setError] = useState('')

  async function cargar() {
    setCargando(true)
    setError('')
    try {
      setDeudas(await api.deudas())
    } catch (err) {
      setError(err.message || 'No se pudieron cargar tus deudas')
    }
    setCargando(false)
  }

  useEffect(() => {
    cargar()
  }, [])

  const totalDeuda = deudas.reduce((s, d) => s + d.saldo_actual, 0)

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={volver}
            className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
           aria-label="Volver">
            <ArrowLeft size={18} />
          </button>
          <h1 className="text-xl font-semibold">Deudas</h1>
        </div>
        <button
          onClick={() => setMostrarForm(true)}
          className="w-10 h-10 rounded-full bg-accent text-white flex items-center justify-center"
         aria-label="Nueva deuda">
          <Plus size={20} />
        </button>
      </header>

      {deudas.length > 0 && (
        <div className="mx-5 mt-3 rounded-2xl bg-danger-soft p-4">
          <p className="text-xs text-ink-soft mb-0.5">Deuda total</p>
          <p className="text-2xl font-bold text-danger">{formatCOP(totalDeuda)}</p>
        </div>
      )}

      {cargando ? (
        <p className="text-sm text-ink-soft text-center mt-8">Cargando...</p>
      ) : error ? (
        <div className="mx-5 mt-6 rounded-2xl bg-danger-soft p-6 text-center">
          <p className="text-sm text-danger mb-3">{error}</p>
          <button onClick={cargar} className="text-sm font-semibold text-danger underline">
            Reintentar
          </button>
        </div>
      ) : deudas.length === 0 ? (
        <div className="mx-5 mt-6 rounded-2xl bg-paper-raised border border-line p-8 text-center">
          <p className="text-sm text-ink-soft">No tienes deudas registradas</p>
        </div>
      ) : (
        <div className="mx-5 mt-4 space-y-3">
          {deudas.map((d, i) => (
            <div key={d.id} className="rounded-2xl bg-paper-raised border border-line p-4 stagger-item" style={{ '--stagger-i': i }}>
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-semibold">{d.nombre}</p>
                <p className="text-sm font-bold">{formatCOP(d.saldo_actual)}</p>
              </div>
              <p className="text-xs text-ink-soft mb-3">
                {d.entidad} · cuota {formatCOP(d.cuota_mensual)}
              </p>
              <div className="flex items-center justify-between text-xs mb-3">
                <span className={urgenciaColor[d.urgencia]}>
                  Pago en {d.dias_para_pago} {d.dias_para_pago === 1 ? 'día' : 'días'}
                </span>
                {d.cuotas_faltantes && <span className="text-ink-soft">{d.cuotas_faltantes} cuotas restantes</span>}
              </div>
              <button
                onClick={() => setPagando(d)}
                className="w-full bg-ink text-paper font-semibold rounded-xl py-2.5 text-sm"
              >
                Registrar pago
              </button>
            </div>
          ))}
        </div>
      )}

      {deudas.length > 0 && !cargando && !error && <SimuladorDeudas />}

      {mostrarForm && (
        <FormDeuda
          onClose={() => setMostrarForm(false)}
          onGuardada={() => {
            setMostrarForm(false)
            cargar()
          }}
        />
      )}

      {pagando && (
        <FormPago
          deuda={pagando}
          onClose={() => setPagando(null)}
          onPagado={async () => {
            setPagando(null)
            await recargarCuentas()
            cargar()
          }}
        />
      )}
    </div>
  )
}

function FormDeuda({ onClose, onGuardada }) {
  const { cuentas } = useCuentas()
  const [nombre, setNombre] = useState('')
  const [entidad, setEntidad] = useState('')
  const [saldoInicial, setSaldoInicial] = useState('')
  const [cuotaMensual, setCuotaMensual] = useState('')
  const [tasaMensual, setTasaMensual] = useState('')
  const [diaPago, setDiaPago] = useState('1')
  const [cuentaPagoId, setCuentaPagoId] = useState(cuentas[0]?.id || '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre')
    if (!saldoInicial || Number(saldoInicial) <= 0) return setError('Ingresa el saldo actual de la deuda')

    setGuardando(true)
    try {
      await api.crearDeuda({
        nombre: nombre.trim(),
        entidad: entidad.trim(),
        saldo_inicial: Number(saldoInicial),
        cuota_mensual: Number(cuotaMensual) || 0,
        tasa_mensual: Number(tasaMensual) || 0,
        dia_pago: Number(diaPago) || 1,
        cuenta_pago_id: cuentaPagoId || null,
      })
      onGuardada()
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50 overflow-y-auto sheet-backdrop">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8 sheet-content">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Nueva deuda</h2>
          <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>

        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Nombre (ej. Tarjeta Visa)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
        />
        <input
          value={entidad}
          onChange={(e) => setEntidad(e.target.value)}
          placeholder="Entidad (ej. Bancolombia)"
          list="entidades-financieras-co"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
        />
        <datalist id="entidades-financieras-co">
          {ENTIDADES_FINANCIERAS_CO.map((e) => (
            <option key={e} value={e} />
          ))}
        </datalist>
        <input
          value={saldoInicial}
          onChange={(e) => setSaldoInicial(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder="Saldo actual de la deuda"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
        />
        <input
          value={cuotaMensual}
          onChange={(e) => setCuotaMensual(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder="Cuota mensual"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
        />
        <input
          value={tasaMensual}
          onChange={(e) => setTasaMensual(e.target.value.replace(/[^0-9.]/g, ''))}
          inputMode="decimal"
          placeholder="Tasa mensual % (opcional)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
        />
        <input
          value={diaPago}
          onChange={(e) => setDiaPago(e.target.value.replace(/\D/g, '').slice(0, 2))}
          inputMode="numeric"
          placeholder="Día de pago (1-31)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
        />

        {cuentas.length > 1 && (
          <label className="block mb-4">
            <span className="text-xs text-ink-soft">Cuenta desde la que pagas</span>
            <select
              value={cuentaPagoId}
              onChange={(e) => setCuentaPagoId(e.target.value)}
              className="w-full mt-1 rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
            >
              {cuentas.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
          </label>
        )}

        {error && <p className="text-sm text-danger mb-3">{error}</p>}

        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : 'Crear deuda'}
        </button>
      </div>
    </div>
  )
}

function FormPago({ deuda, onClose, onPagado }) {
  const [monto, setMonto] = useState(String(deuda.cuota_mensual || ''))
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!monto || Number(monto) <= 0) return setError('Ingresa un monto válido')

    setGuardando(true)
    try {
      await api.pagarDeuda(deuda.id, Number(monto))
      onPagado()
    } catch (err) {
      setError(err.message || 'No se pudo registrar el pago')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50 sheet-backdrop">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8 sheet-content">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Pagar "{deuda.nombre}"</h2>
          <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>

        <input
          value={monto}
          onChange={(e) => setMonto(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder="Monto a pagar"
          autoFocus
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
        />

        {error && <p className="text-sm text-danger mb-3">{error}</p>}

        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : 'Registrar pago'}
        </button>
      </div>
    </div>
  )
}
