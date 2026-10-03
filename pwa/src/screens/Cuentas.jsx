import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Link } from 'react-router-dom'
import { ArrowLeft, Pencil, Plus, Trash2, Users, X } from 'lucide-react'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'
import { ENTIDADES_FINANCIERAS_CO } from '../lib/entidadesFinancierasCO'
import TarjetaCuenta from '../components/TarjetaCuenta'
import BotonOjo from '../components/BotonOjo'

const iconos = ['🏦', '💜', '💵', '💳', '📈']
const tipos = [
  { id: 'ahorro', label: 'Ahorros' },
  { id: 'efectivo', label: 'Efectivo' },
  { id: 'credito', label: 'Crédito' },
  { id: 'inversion', label: 'Inversión' },
]
const tipoLabel = Object.fromEntries(tipos.map((t) => [t.id, t.label]))

export default function Cuentas() {
  const navigate = useNavigate()
  const { cuentas, cargando, error, recargar } = useCuentas()
  const [mostrarForm, setMostrarForm] = useState(false)
  const [editando, setEditando] = useState(null)

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pt-14 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="w-9 h-9 flex items-center justify-center -ml-2" aria-label="Volver">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-bold">Tus cuentas</h1>
        </div>
        <div className="flex items-center gap-2">
          <BotonOjo />
          <button
            onClick={() => setMostrarForm(true)}
            className="w-9 h-9 rounded-full bg-accent text-white flex items-center justify-center"
           aria-label="Nueva cuenta">
            <Plus size={18} />
          </button>
        </div>
      </header>

      <p className="mx-6 mt-2 text-xs text-ink-soft">
        Cada cuenta es un lugar donde tienes o debes plata: tu Bancolombia, tu Nequi, el efectivo
        en tu bolsillo. El saldo de todas juntas es lo que ves como "Saldo total" en Inicio.
      </p>

      {cargando ? (
        <p className="text-sm text-ink-soft text-center mt-8">Cargando...</p>
      ) : error ? (
        <div className="mx-6 mt-6 rounded-2xl bg-danger-soft p-6 text-center">
          <p className="text-sm text-danger mb-3">{error}</p>
        </div>
      ) : cuentas.length === 0 ? (
        <div className="mx-6 mt-6 rounded-2xl bg-paper-raised border border-line p-8 text-center">
          <p className="text-sm text-ink-soft">Aún no tienes cuentas</p>
        </div>
      ) : (
        <div className="mx-6 mt-4 space-y-3">
          {cuentas.map((c, i) => (
            <div key={c.id} className="flex items-center gap-3 stagger-item" style={{ '--stagger-i': i }}>
              <TarjetaCuenta cuenta={c} className="flex-1" />
              <div className="flex flex-col items-center gap-1 shrink-0">
                <button
                  onClick={() => setEditando(c)}
                  className="w-9 h-9 flex items-center justify-center text-ink-soft"
                  aria-label="Editar cuenta"
                >
                  <Pencil size={16} />
                </button>
                <span className="text-[10px] text-ink-soft">{tipoLabel[c.tipo] || c.tipo}</span>
              </div>
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

const MONEDAS = ['COP', 'USD', 'EUR']

function FormCuenta({ cuenta, onClose, onGuardada, onEliminada }) {
  const esEdicion = !!cuenta
  const [nombre, setNombre] = useState(cuenta?.nombre || '')
  const [tipo, setTipo] = useState(cuenta?.tipo || 'ahorro')
  const [icono, setIcono] = useState(cuenta?.icono || '🏦')
  const [moneda, setMoneda] = useState(cuenta?.moneda || 'COP')
  const [saldoInicial, setSaldoInicial] = useState('')
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
        await api.editarCuenta(cuenta.id, { nombre: nombre.trim(), tipo, icono })
      } else {
        await api.crearCuenta({ nombre: nombre.trim(), tipo, icono, moneda, saldo: Number(saldoInicial) || 0 })
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
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50 sheet-backdrop">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8 max-h-[90vh] overflow-y-auto sheet-content">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{esEdicion ? 'Editar cuenta' : 'Nueva cuenta'}</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>

        <div className="flex gap-2 justify-center mb-5">
          {iconos.map((ic) => (
            <button
              key={ic}
              onClick={() => setIcono(ic)}
              className={`w-12 h-12 rounded-2xl border-2 flex items-center justify-center text-xl ${
                icono === ic ? 'border-accent bg-accent-soft' : 'border-line'
              }`}
            >
              {ic}
            </button>
          ))}
        </div>

        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Nombre de la cuenta (ej. Bancolombia Ahorro)"
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
              onClick={() => setTipo(t.id)}
              className={`rounded-2xl border py-3 text-sm font-medium ${
                tipo === t.id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {!esEdicion && (
          <>
            <div className="mb-3">
              <p className="text-xs text-ink-soft mb-1.5">Moneda</p>
              <div className="flex gap-2" role="group" aria-label="Moneda de la cuenta">
                {MONEDAS.map((m) => (
                  <button
                    key={m}
                    type="button"
                    aria-pressed={moneda === m}
                    onClick={() => setMoneda(m)}
                    className={`flex-1 rounded-2xl border py-2.5 text-sm font-medium ${
                      moneda === m ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
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
      </div>
    </div>
  )
}
