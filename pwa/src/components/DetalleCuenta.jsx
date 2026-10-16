import { useEffect, useState } from 'react'
import { EsqueletoTexto } from './Esqueletos'
import { Link, useNavigate } from 'react-router-dom'
import { FileUp, Scale, X } from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { cupoDisponible, deudaTarjeta, esCredito, etiquetaCuenta, textoActualizado } from '../lib/saldos'
import Ayudita from './Ayudita'
import { CajitasDeCuenta } from './TuPlataTrabajando'
import Hoja from './Hoja'
import { leerMonto } from '../lib/cuentaNueva'
import { fechaHoraMovimiento, fechaDeMovimiento } from '../lib/fechaMovimiento'
import { TarjetaCuadreBanco } from './CuadreMes'
import InputMonto from './InputMonto'

// Detalle de UNA cuenta: saldo actual sin ambigüedad, cómo va el mes, últimos
// movimientos y las dos acciones para que el saldo coincida con el banco:
//  - Ajustar saldo: escribes el saldo real y la app crea un movimiento "Ajuste de saldo"
//    que mueve el saldo pero NO cuenta como gasto ni ingreso en los reportes.
//  - Comparar con mi banco: sube el extracto o un Excel/CSV y se comparan movimientos.
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
      setError(err.message || 'No se pudo cargar la cuenta. Revisa tu conexión e intenta de nuevo.')
    }
  }

  useEffect(() => {
    cargar()
  }, [cuentaId])

  const c = det?.cuenta
  const credito = c && esCredito(c)

  return (
    <Hoja onCerrar={onClose} historial={false}>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">{c?.nombre || 'Cuenta'}</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {!det && !error && <EsqueletoTexto lineas={4} etiqueta="Cargando la cuenta" />}

      {det && (
        <>
          <div className="rounded-2xl bg-paper-raised border border-line p-4">
            <p className="text-[11px] font-semibold text-accent" data-testid="tipo-cuenta">{etiquetaCuenta(c).etiqueta}</p>
            <p className="t-kicker text-ink-soft mt-1">{credito ? 'Debes' : 'Saldo actual'}</p>
            <p className="text-3xl t-display mt-1" data-testid="saldo-detalle">
              {fmt(credito ? deudaTarjeta(c) : det.saldo_actual, c.moneda)}
            </p>
            <p className="text-xs text-ink-soft mt-1">{textoActualizado(det.ultimo_movimiento)}</p>
            <p className="text-xs text-ink-soft mt-2" data-testid="significado-saldo">
              {etiquetaCuenta(c).significado} <Ayudita termino={etiquetaCuenta(c).termino} />
            </p>
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
            No incluyen pagos de tarjeta, la plata que pasaste entre tus cuentas ni ajustes de saldo.
          </p>

          {c.tipo === 'ahorro' && <CajitasDeCuenta cuentaId={c.id} />}

          {c.tipo !== 'efectivo' && <TarjetaCuadreBanco cuentaId={c.id} moneda={c.moneda} onCambio={cargar} />}

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
              onClick={() => navigate('/sincronizacion', { state: { abrir: 'subir' } })}
              className="flex items-center justify-center gap-2 rounded-2xl border border-line bg-paper-raised py-3.5 text-sm font-semibold"
            >
              <FileUp size={16} className="text-accent" /> Comparar con mi banco
            </button>
            <p className="text-[11px] text-ink-soft text-center">
              Sube el extracto en PDF, o <Link to="/sincronizacion" state={{ abrir: 'subir', manual: true }} className="text-accent font-medium">importa un Excel o CSV</Link> del banco.
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
                <Link key={m.id} to={`/movimientos/${m.id}`} className="flex items-start gap-3 px-4 py-3 min-h-[56px]">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold break-words line-clamp-3">{m.descripcion}</p>
                    <p className="text-xs text-ink-soft mt-0.5 break-words">{fechaHoraMovimiento(fechaDeMovimiento(m))}</p>
                    <p className="text-xs text-ink-soft break-words">
                      {m.fuente === 'ajuste_saldo' ? 'No cuenta como gasto ni ingreso' : m.categoria}
                    </p>
                  </div>
                  <span className={`text-sm font-semibold shrink-0 whitespace-nowrap tabular-nums ${m.tipo === 'income' ? 'text-accent' : ''}`}>
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
  const monto = leerMonto(valor)
  const nuevoSaldo = valor === '' ? null : credito ? -Math.abs(monto) : valor.trim().startsWith('-') ? -monto : monto
  const diferencia = nuevoSaldo === null ? null : nuevoSaldo - (cuenta.saldo || 0)

  async function guardar() {
    setError('')
    if (nuevoSaldo === null || Number.isNaN(nuevoSaldo)) return setError('Escribe el saldo que ves en tu banco')
    setGuardando(true)
    try {
      await api.ajustarSaldo(cuenta.id, nuevoSaldo)
      await onHecho()
    } catch (err) {
      setError(err.message || 'No se pudo ajustar el saldo. Revisa tu conexión e intenta de nuevo.')
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
        <InputMonto negativo
          value={valor}
          onValor={setValor}
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
        className="w-full mt-3 bg-accent text-paper-raised font-semibold rounded-2xl py-3 text-sm disabled:opacity-60"
      >
        {guardando ? 'Ajustando...' : 'Confirmar ajuste'}
      </button>
    </div>
  )
}
