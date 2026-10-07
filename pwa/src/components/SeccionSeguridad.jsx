import { useEffect, useState } from 'react'
import { Fingerprint, ShieldCheck } from 'lucide-react'
import { useBloqueo } from '../lib/BloqueoContext'
import { useAuth } from '../lib/AuthContext'
import { useDialogos } from '../lib/DialogosContext'
import {
  OPCIONES_BLOQUEO,
  activarBiometria,
  biometriaActiva,
  biometriaDisponible,
  desactivarBiometria,
  guardarMinutosBloqueo,
  minutosBloqueo,
  pinValido,
  verificarPin,
} from '../lib/seguridad'

const etiqueta = (min) => (min === 0 ? 'Al salir de la app' : min === 1 ? 'Tras 1 minuto' : `Tras ${min} minutos`)

function Interruptor({ activo, onClick, etiquetaAria, deshabilitado }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={deshabilitado}
      role="switch"
      aria-checked={activo}
      aria-label={etiquetaAria}
      className={`shrink-0 w-12 h-7 rounded-full transition-colors relative ${activo ? 'bg-accent' : 'bg-line'} disabled:opacity-60`}
    >
      <span className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${activo ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  )
}

// Formulario para crear un PIN (4-6 dígitos) o pedir el actual para desactivarlo.
function FormPin({ titulo, boton, pedirConfirmacion, onListo, onCancelar }) {
  const [pin, setPin] = useState('')
  const [repetido, setRepetido] = useState('')
  const [error, setError] = useState('')
  const [trabajando, setTrabajando] = useState(false)
  const soloDigitos = (v) => v.replace(/\D/g, '').slice(0, 6)

  async function enviar(e) {
    e.preventDefault()
    setError('')
    if (!pinValido(pin)) return setError('El PIN debe tener entre 4 y 6 dígitos')
    if (pedirConfirmacion && pin !== repetido) return setError('Los PIN no coinciden')
    setTrabajando(true)
    try {
      await onListo(pin)
    } catch (err) {
      setError(err.message || 'No se pudo completar')
      setTrabajando(false)
    }
  }

  return (
    <form onSubmit={enviar} className="mt-3 pt-3 border-t border-line space-y-2">
      <p className="text-sm font-medium">{titulo}</p>
      <input
        type="password" inputMode="numeric" autoComplete="off" value={pin} aria-label="PIN"
        onChange={(e) => setPin(soloDigitos(e.target.value))} placeholder="PIN de 4 a 6 dígitos"
        className="w-full rounded-2xl border border-line bg-paper px-4 py-3 text-sm outline-none focus:border-accent"
      />
      {pedirConfirmacion && (
        <input
          type="password" inputMode="numeric" autoComplete="off" value={repetido} aria-label="Repite el PIN"
          onChange={(e) => setRepetido(soloDigitos(e.target.value))} placeholder="Repite el PIN"
          className="w-full rounded-2xl border border-line bg-paper px-4 py-3 text-sm outline-none focus:border-accent"
        />
      )}
      {error && <p role="alert" className="text-xs text-danger">{error}</p>}
      <div className="flex gap-2">
        <button type="button" onClick={onCancelar} className="flex-1 rounded-2xl border border-line py-2.5 text-sm">Cancelar</button>
        <button type="submit" disabled={trabajando} className="flex-1 rounded-2xl bg-ink text-paper py-2.5 text-sm font-semibold disabled:opacity-60">
          {boton}
        </button>
      </div>
    </form>
  )
}

export default function SeccionSeguridad() {
  const { tienePin, definirPin, quitarPin } = useBloqueo()
  const { usuario } = useAuth()
  const { avisar } = useDialogos()
  const [modo, setModo] = useState(null) // 'crear' | 'quitar'
  const [minutos, setMinutos] = useState(() => minutosBloqueo())
  const [bioOk, setBioOk] = useState(false)
  const [bioActiva, setBioActiva] = useState(() => biometriaActiva())

  useEffect(() => {
    biometriaDisponible().then(setBioOk)
  }, [])

  async function crear(pin) {
    await definirPin(pin)
    setModo(null)
  }

  async function quitar(pin) {
    if (!(await verificarPin(pin))) throw new Error('PIN incorrecto')
    quitarPin()
    setBioActiva(false)
    setModo(null)
  }

  async function alternarBio() {
    if (bioActiva) {
      desactivarBiometria()
      return setBioActiva(false)
    }
    try {
      await activarBiometria(usuario?.email)
      setBioActiva(true)
    } catch {
      avisar('No se pudo activar la huella o el rostro. Puedes seguir usando tu PIN.')
    }
  }

  return (
    <section className="mx-6 mt-6">
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheck size={16} className="text-ink-soft" />
        <h2 className="text-[15px] font-semibold">Seguridad</h2>
      </div>
      <div className="rounded-2xl bg-paper-raised border border-line p-4">
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <p className="text-sm font-medium">PIN para abrir la app</p>
            <p className="text-xs text-ink-soft mt-0.5">
              Se guarda solo en este dispositivo (como hash). Nunca llega a nuestros servidores.
            </p>
          </div>
          <Interruptor
            activo={tienePin}
            etiquetaAria="PIN para abrir la app"
            onClick={() => setModo(tienePin ? 'quitar' : 'crear')}
          />
        </div>

        {modo === 'crear' && (
          <FormPin titulo="Crea tu PIN" boton="Guardar PIN" pedirConfirmacion onListo={crear} onCancelar={() => setModo(null)} />
        )}
        {modo === 'quitar' && (
          <FormPin titulo="Escribe tu PIN actual para quitarlo" boton="Quitar PIN" onListo={quitar} onCancelar={() => setModo(null)} />
        )}

        {tienePin && (
          <>
            <div className="mt-4 pt-3 border-t border-line">
              <label htmlFor="bloqueo-min" className="text-sm font-medium">Bloquear automáticamente</label>
              <select
                id="bloqueo-min"
                value={minutos}
                onChange={(e) => {
                  const n = Number(e.target.value)
                  setMinutos(n)
                  guardarMinutosBloqueo(n)
                }}
                className="w-full mt-2 rounded-2xl border border-line bg-paper px-4 py-3 text-sm outline-none focus:border-accent"
              >
                {OPCIONES_BLOQUEO.map((m) => (
                  <option key={m} value={m}>{etiqueta(m)}</option>
                ))}
              </select>
              <p className="text-xs text-ink-soft mt-1">Tiempo que puede estar la app en segundo plano antes de pedir el PIN.</p>
            </div>

            {bioOk && (
              <div className="mt-4 pt-3 border-t border-line flex items-center gap-3">
                <Fingerprint size={20} className="text-accent shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-medium">Huella o Face ID</p>
                  <p className="text-xs text-ink-soft mt-0.5">El PIN siempre queda como respaldo</p>
                </div>
                <Interruptor activo={bioActiva} etiquetaAria="Huella o Face ID" onClick={alternarBio} />
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}
