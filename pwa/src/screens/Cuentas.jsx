import { useEffect, useState } from 'react'
import { EstadoVacio } from '../brand/Marca'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { Link } from 'react-router-dom'
import { useBloqueo } from '../lib/BloqueoContext'
import { textoActualizado } from '../lib/saldos'
import DetalleCuenta from '../components/DetalleCuenta'
import ResumenSaldo from '../components/ResumenSaldo'
import { ArrowLeft, Pencil, Plus, Trash2, Users, X, Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'
import { ENTIDADES_FINANCIERAS_CO } from '../lib/entidadesFinancierasCO'
import TarjetaCuenta from '../components/TarjetaCuenta'
import SelectorCuenta from '../components/SelectorCuenta'
import PanelTarjetaCredito from '../components/PanelTarjetaCredito'
import BotonOjo from '../components/BotonOjo'
import Hoja from '../components/Hoja'

const tipos = [
  { id: 'ahorro', label: 'Ahorros' },
  { id: 'efectivo', label: 'Efectivo' },
  { id: 'credito', label: 'Crédito' },
  { id: 'inversion', label: 'Inversión' },
]
const tipoLabel = Object.fromEntries(tipos.map((t) => [t.id, t.label]))

export default function Cuentas() {
  const volver = useVolver('/')
  const { cuentas, cargando, error, recargar } = useCuentas()
  const [mostrarForm, setMostrarForm] = useState(false)
  const [editando, setEditando] = useState(null)
  const { fmt } = useBloqueo()
  const [params, setParams] = useSearchParams()
  const [resumen, setResumen] = useState(null)
  // El detalle se abre con ?cuenta=<id> (así también se llega desde el mazo de Inicio).
  const detalleId = params.get('cuenta')

  function cargarResumen() {
    Promise.resolve().then(() => api.resumenCuentas()).then(setResumen).catch(() => {})
  }
  useEffect(cargarResumen, [])

  // Abrir el detalle desde la lista agrega una entrada de historial (atrás lo cierra, como
  // en cualquier hoja); cerrarlo con X/Escape/tocar fuera deshace esa entrada. Si se llegó
  // directo con ?cuenta= (mazo de Inicio, enlace) no hay entrada propia: se reemplaza.
  const navigate = useNavigate()
  const location = useLocation()
  function abrirDetalle(id) {
    setParams({ cuenta: id }, { state: { detalleDesdeLista: true } })
  }
  function cerrarDetalle() {
    if (location.state?.detalleDesdeLista) navigate(-1)
    else setParams({}, { replace: true })
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-bold">Tus cuentas</h1>
        </div>
        <div className="flex items-center gap-2">
          <BotonOjo />
          <button
            onClick={() => setMostrarForm(true)}
            className="w-11 h-11 rounded-full bg-accent text-white flex items-center justify-center"
           aria-label="Nueva cuenta">
            <Plus size={18} />
          </button>
        </div>
      </header>

      <p className="mx-6 mt-2 text-xs text-ink-soft">
        Cada cuenta es un lugar donde tienes o debes plata: tu Bancolombia, tu Nequi, el efectivo
        en tu bolsillo. El saldo de todas juntas es el «Saldo actual» de Inicio. Toca una cuenta
        para ver su detalle o ajustar su saldo si no coincide con tu banco.
      </p>

      {resumen && cuentas.length > 0 && (
        <section className="mx-6 mt-3 hero-marca card-marca p-4" aria-label="Saldo actual total">
          <p className="t-kicker">Saldo actual total</p>
          <p className="text-3xl t-display mt-1.5">{fmt(resumen.total_cop)}</p>
          <p className="text-xs mt-1 opacity-85">En pesos · {textoActualizado(resumen.ultimo_movimiento)}</p>
          <ResumenSaldo resumen={resumen} className="mt-3" />
        </section>
      )}

      {cargando ? (
        <p className="text-sm text-ink-soft text-center mt-8">Cargando...</p>
      ) : error ? (
        <div className="mx-6 mt-6 rounded-2xl bg-danger-soft p-6 text-center">
          <p className="text-sm text-danger mb-3">{error}</p>
        </div>
      ) : cuentas.length === 0 ? (
        <EstadoVacio icono={Wallet} titulo="Aún no tienes cuentas" texto="Agrega la primera con el botón +." className="mx-6 mt-6" />
      ) : (
        <div className="mx-6 mt-4 space-y-3">
          {cuentas.map((c, i) => (
            <div key={c.id} className="stagger-item" style={{ '--stagger-i': i }}>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => abrirDetalle(c.id)}
                  className="flex-1 min-w-0 text-left"
                  aria-label={`Ver detalle de ${c.nombre}`}
                >
                  <TarjetaCuenta cuenta={c} ultimoMovimiento={resumen ? (resumen.ultimo_por_cuenta?.[c.id] ?? null) : undefined} />
                </button>
                <div className="flex flex-col items-center gap-1 shrink-0">
                  <button
                    onClick={() => setEditando(c)}
                    className="w-11 h-11 flex items-center justify-center text-ink-soft"
                    aria-label="Editar cuenta"
                  >
                    <Pencil size={16} />
                  </button>
                  <span className="text-[11px] text-ink-soft">{tipoLabel[c.tipo] || c.tipo}</span>
                </div>
              </div>
              {/* Las cuentas de crédito son tarjetas reales: cupo, corte y pago */}
              {c.tipo === 'credito' && <PanelTarjetaCredito cuenta={c} onCambio={recargar} />}
            </div>
          ))}

          <Link
            to="/compartir"
            className="flex items-center justify-center gap-2 text-sm text-accent font-medium py-2"
          >
            <Users size={15} /> Compartir una cuenta con alguien
          </Link>
        </div>
      )}

      {detalleId && cuentas.some((c) => c.id === detalleId) && (
        <DetalleCuenta
          cuentaId={detalleId}
          onClose={cerrarDetalle}
          onCambio={() => {
            recargar()
            cargarResumen()
          }}
        />
      )}

      {mostrarForm && (
        <FormCuenta
          onClose={() => setMostrarForm(false)}
          onGuardada={() => {
            setMostrarForm(false)
            recargar()
          }}
        />
      )}

      {editando && (
        <FormCuenta
          cuenta={editando}
          onClose={() => setEditando(null)}
          onGuardada={() => {
            setEditando(null)
            recargar()
          }}
          onEliminada={() => {
            setEditando(null)
            recargar()
          }}
        />
      )}
    </div>
  )
}


function FormCuenta({ cuenta, onClose, onGuardada, onEliminada }) {
  const esEdicion = !!cuenta
  const [nombre, setNombre] = useState(cuenta?.nombre || '')
  const [tipo, setTipo] = useState(cuenta?.tipo || 'ahorro')
  const [icono, setIcono] = useState(cuenta?.icono || '🏦')
  const [moneda, setMoneda] = useState(cuenta?.moneda || 'COP')
  const [saldoInicial, setSaldoInicial] = useState('')
  const [alias, setAlias] = useState(cuenta?.alias_tarjeta || '')
  const [guardando, setGuardando] = useState(false)
  const [eliminando, setEliminando] = useState(false)
  const [error, setError] = useState('')
  const { confirmar } = useDialogos()

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a tu cuenta')

    setGuardando(true)
    try {
      if (esEdicion) {
        await api.editarCuenta(cuenta.id, { nombre: nombre.trim(), tipo, icono, alias_tarjeta: alias.trim() })
      } else {
        await api.crearCuenta({
          nombre: nombre.trim(), tipo, icono, moneda, saldo: Number(saldoInicial) || 0,
          ...(alias.trim() ? { alias_tarjeta: alias.trim() } : {}),
        })
      }
      onGuardada()
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  async function eliminar() {
    const ok = await confirmar('Esto solo funciona si la cuenta no tiene movimientos.', {
      titulo: `¿Eliminar "${cuenta.nombre}"?`,
      confirmarTexto: 'Eliminar',
      peligro: true,
    })
    if (!ok) return
    setEliminando(true)
    setError('')
    try {
      await api.eliminarCuenta(cuenta.id)
      onEliminada()
    } catch (err) {
      setError(err.message || 'No se pudo eliminar')
      setEliminando(false)
    }
  }

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">{esEdicion ? 'Editar cuenta' : 'Nueva cuenta'}</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      {esEdicion ? (
        <>
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Nombre de la cuenta (ej. Bancolombia Ahorro)"
            aria-label="Nombre de la cuenta"
            list="entidades-financieras-co-cuentas"
            className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
          />
          <datalist id="entidades-financieras-co-cuentas">
            {ENTIDADES_FINANCIERAS_CO.map((e) => (
              <option key={e} value={e} />
            ))}
          </datalist>
          <div className="grid grid-cols-2 gap-2 mb-4">
            {tipos.map((t) => (
              <button
                key={t.id}
                type="button"
                aria-pressed={tipo === t.id}
                onClick={() => setTipo(t.id)}
                className={`rounded-2xl border py-3 text-sm font-medium min-h-[44px] ${
                  tipo === t.id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </>
      ) : (
        <div className="mb-4">
          <SelectorCuenta
            nombre={nombre}
            setNombre={setNombre}
            tipo={tipo}
            setTipo={setTipo}
            setIcono={setIcono}
            moneda={moneda}
            setMoneda={setMoneda}
          />
        </div>
      )}

      {!esEdicion && (
        <>
          <input
            value={saldoInicial}
            onChange={(e) => setSaldoInicial(e.target.value.replace(/[^\d.]/g, ''))}
            inputMode="decimal"
            placeholder="Saldo actual (opcional)"
            aria-label="Saldo actual"
            className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
          />
        </>
      )}

      <label className="block mb-4">
        <span className="text-xs font-medium text-ink-soft">Alias de la tarjeta en Wallet (opcional)</span>
        <input
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          maxLength={120}
          placeholder="ej. Visa Bancolombia, 1234"
          aria-label="Alias de tarjeta"
          className="w-full mt-1 rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm outline-none focus:border-accent"
        />
        <span className="block text-[11px] text-ink-soft mt-1">
          Cuando pagues con el celular, asignamos el pago a esta cuenta si el nombre de la tarjeta contiene este texto.
          Puedes poner varios separados por coma.
        </span>
      </label>

      {esEdicion && (
        <p className="text-xs text-ink-soft mb-4">
          El saldo se ajusta solo registrando movimientos, no se edita aquí directamente.
        </p>
      )}

      {error && <p className="text-sm text-danger mb-3">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
      >
        {guardando ? 'Guardando...' : esEdicion ? 'Guardar cambios' : 'Crear cuenta'}
      </button>

      {esEdicion && (
        <button
          onClick={eliminar}
          disabled={eliminando}
          className="w-full flex items-center justify-center gap-1.5 mt-3 text-sm text-danger font-medium disabled:opacity-60"
        >
          <Trash2 size={14} /> {eliminando ? 'Eliminando...' : 'Eliminar cuenta'}
        </button>
      )}
    </Hoja>
  )
}
