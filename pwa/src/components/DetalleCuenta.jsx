import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FileUp, Scale, X } from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { cupoDisponible, deudaTarjeta, esCredito, textoActualizado } from '../lib/saldos'
import Hoja from './Hoja'

// Detalle de UNA cuenta: saldo actual sin ambigüedad, cómo va el mes, últimos
// movimientos y las dos acciones para que el saldo coincida con el banco:
//  - Ajustar saldo: escribes el saldo real y la app crea un movimiento "Ajuste de saldo"
//    que mueve el saldo pero NO cuenta como gasto ni ingreso en los reportes.
//  - Conciliar con mi banco: sube el extracto o un Excel/CSV y se comparan movimientos.
export default function DetalleCuenta({ cuentaId, onClose, onCambio }) {
  const { fmt } = useBloqueo()
  const navigate = useNavigate()
  const [det, setDet] = useState(null)
  const [error, setError] = useState('')
  const [ajustando, setAjustando] = useState(false)

  async function cargar() {
    try {
      setDet(await api.detalleCuenta(cuentaId))
    } catch (err) {
      setError(err.message || 'No se pudo cargar la cuenta')
    }
  }

  useEffect(() => {
    cargar()
  }, [cuentaId])

  const c = det?.cuenta
  const credito = c && esCredito(c)

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">{c?.nombre || 'Cuenta'}</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {!det && !error && <p className="text-sm text-ink-soft">Cargando...</p>}

      {det && (
        <>
          <div className="rounded-2xl bg-paper-raised border border-line p-4">
            <p className="t-kicker text-ink-soft">{credito ? 'Debes' : 'Saldo actual'}</p>
            <p className="text-3xl t-display mt-1" data-testid="saldo-detalle">
              {fmt(credito ? deudaTarjeta(c) : det.saldo_actual, c.moneda)}
            </p>
            <p className="text-xs text-ink-soft mt-1">{textoActualizado(det.ultimo_movimiento)}</p>
            {credito && cupoDisponible(c) != null && (
              <p className="text-sm mt-2">
                <span className="text-ink-soft">Disponible del cupo: </span>
                <span className="font-semibold">{fmt(cupoDisponible(c), c.moneda)}</span>
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 mt-3">
            <div className="rounded-2xl bg-paper-raised border border-line p-3">
              <p className="text-xs text-ink-soft">Ingresos del mes</p>
              <p className="text-sm font-bold text-accent mt-0.5">{fmt(det.ingresos_mes, c.moneda)}</p>
            </div>
            <div className="rounded-2xl bg-paper-raised border border-line p-3">
              <p className="text-xs text-ink-soft">Gastos del mes</p>
              <p className="text-sm font-bold mt-0.5">{fmt(det.gastos_mes, c.moneda)}</p>
            </div>
          </div>
          <p className="text-[11px] text-ink-soft mt-1.5">
            No incluyen pagos de tarjeta, traslados entre tus cuentas ni ajustes de saldo.
          </p>

          <div className="grid grid-cols-1 gap-2 mt-4">
            <button
              onClick={() => setAjustando((v) => !v)}
              aria-expanded={ajustando}
              className="flex items-center justify-center gap-2 bg-ink text-paper font-semibold rounded-2xl py-3.5 text-sm"
            >
              <Scale size={16} /> Ajustar saldo
            </button>
            {ajustando && (
              <FormAjuste
                cuenta={c}
                onHecho={async () => {
                  setAjustando(false)
                  await cargar()
                  onCambio?.()
                }}
              />
            )}
            <button
              onClick={() => navigate('/conciliacion')}
              className="flex items-center justify-center gap-2 rounded-2xl border border-line bg-paper-raised py-3.5 text-sm font-semibold"
            >
              <FileUp size={16} className="text-accent" /> Conciliar con mi banco
            </button>
            <p className="text-[11px] text-ink-soft text-center">
              Sube el extracto en PDF, o <Link to="/importar" className="text-accent font-medium">importa un Excel o CSV</Link> del banco.
            </p>
          </div>

          <h3 className="text-sm font-semibold mt-5 mb-2">Últimos movimientos</h3>
          {det.movimientos.length === 0 ? (
            <p className="text-xs text-ink-soft rounded-2xl bg-paper-raised border border-line p-4">
              Esta cuenta aún no tiene movimientos. El saldo es lo que tienes hoy en ella: si no coincide con tu banco, usa «Ajustar saldo».
            </p>
          ) : (
            <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line">
              {det.movimientos.map((m) => (
                <Link key={m.id} to={`/movimientos/${m.id}`} className="flex items-center gap-3 px-4 py-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{m.descripcion}</p>
                    <p className="text-xs text-ink-soft">
                      {m.fuente === 'ajuste_saldo' ? 'No cuenta como gasto ni ingreso' : m.categoria}
                    </p>
                  </div>
                  <span className={`text-sm font-semibold shrink-0 ${m.tipo === 'income' ? 'text-accent' : ''}`}>
                    {m.tipo === 'income' ? '+' : m.tipo === 'expense' ? '-' : ''}
                    {fmt(m.monto, c.moneda)}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </Hoja>
  )
}

function FormAjuste({ cuenta, onHecho }) {
  const credito = esCredito(cuenta)
  const [valor, setValor] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const { fmt } = useBloqueo()

  // En tarjetas se escribe lo que se DEBE (positivo); el backend guarda el saldo en negativo.
  const nuevoSaldo = valor === '' ? null : credito ? -Number(valor) : Number(valor)
  const diferencia = nuevoSaldo === null ? null : nuevoSaldo - (cuenta.saldo || 0)

  async function guardar() {
    setError('')
    if (nuevoSaldo === null || Number.isNaN(nuevoSaldo)) return setError('Escribe el saldo que ves en tu banco')
    setGuardando(true)
    try {
      await api.ajustarSaldo(cuenta.id, nuevoSaldo)
      await onHecho()
    } catch (err) {
      setError(err.message || 'No se pudo ajustar el saldo')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="rounded-2xl border border-line bg-paper-raised p-4" aria-label="Ajustar saldo">
      <label className="block">
        <span className="text-xs text-ink-soft">
          {credito ? '¿Cuánto debes hoy en esta tarjeta?' : '¿Cuál es el saldo real que ves en tu banco?'}
        </span>
        <input
          value={valor}
          onChange={(e) => setValor(e.target.value.replace(/[^\d.-]/g, ''))}
          inputMode="decimal"
          placeholder="Ej. 1500000"
          aria-label={credito ? 'Lo que debes hoy' : 'Saldo real'}
          className="w-full rounded-2xl border border-line bg-paper px-4 py-3.5 text-sm outline-none focus:border-accent mt-1"
        />
      </label>
      {diferencia !== null && !Number.isNaN(diferencia) && (
        <p className="text-xs mt-2" data-testid="vista-previa-ajuste">
          {Math.abs(diferencia) < 0.005
            ? 'Ya coincide: no hace falta ajustar nada.'
            : `Crearemos un «Ajuste de saldo» de ${diferencia > 0 ? '+' : '-'}${fmt(Math.abs(diferencia), cuenta.moneda)}. No cuenta como gasto ni ingreso en tus reportes.`}
        </p>
      )}
      {error && <p role="alert" className="text-xs text-danger mt-2">{error}</p>}
      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full mt-3 bg-accent text-white font-semibold rounded-2xl py-3 text-sm disabled:opacity-60"
      >
        {guardando ? 'Ajustando...' : 'Confirmar ajuste'}
      </button>
    </div>
  )
}
