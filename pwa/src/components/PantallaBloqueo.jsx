import { useEffect, useRef, useState } from 'react'
import { Delete, Fingerprint, Lock } from 'lucide-react'
import { useBloqueo } from '../lib/BloqueoContext'
import { useAuth } from '../lib/AuthContext'
import {
  biometriaActiva,
  estadoIntentos,
  limpiarFallos,
  registrarFallo,
  verificarBiometria,
  verificarPin,
} from '../lib/seguridad'

const TECLAS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'bio', '0', 'borrar']

// Pantalla completa que tapa la app mientras está bloqueada. El PIN tiene 4-6
// dígitos y no sabemos cuántos eligió, así que se confirma con el botón "Entrar"
// (o automáticamente al llegar a 6).
export default function PantallaBloqueo() {
  const { desbloquear } = useBloqueo()
  const { logout } = useAuth()
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [espera, setEspera] = useState(() => estadoIntentos().espera)
  const [verificando, setVerificando] = useState(false)
  const intentoBio = useRef(false)
  const bio = biometriaActiva()

  async function probarBiometria() {
    if (await verificarBiometria()) {
      limpiarFallos()
      desbloquear()
    }
  }

  // Al abrir, si hay huella/Face ID se ofrece de una vez (una sola vez por pantalla).
  useEffect(() => {
    if (bio && !intentoBio.current) {
      intentoBio.current = true
      probarBiometria()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Cuenta regresiva cuando hay demasiados intentos fallidos.
  useEffect(() => {
    if (espera <= 0) return
    const t = setTimeout(() => setEspera(estadoIntentos().espera), 1000)
    return () => clearTimeout(t)
  }, [espera])

  async function confirmar(valor = pin) {
    if (valor.length < 4 || verificando || espera > 0) return
    setVerificando(true)
    const ok = await verificarPin(valor)
    setVerificando(false)
    if (ok) {
      limpiarFallos()
      desbloquear()
      return
    }
    const { espera: e } = registrarFallo()
    setEspera(e)
    setError(e > 0 ? `Demasiados intentos. Espera ${e} s` : 'PIN incorrecto')
    setPin('')
  }

  function tocar(t) {
    setError('')
    if (t === 'borrar') return setPin((p) => p.slice(0, -1))
    if (t === 'bio') return bio && probarBiometria()
    if (pin.length >= 6) return
    const nuevo = pin + t
    setPin(nuevo)
    if (nuevo.length === 6) confirmar(nuevo)
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="App bloqueada" className="fixed inset-0 z-[100] bg-paper flex justify-center sheet-backdrop">
      <div className="w-full max-w-[480px] flex flex-col items-center px-8 pt-20 pb-8">
        <div className="w-14 h-14 rounded-full bg-accent-soft flex items-center justify-center pop-in">
          <Lock size={24} className="text-accent" />
        </div>
        <h1 className="text-xl font-bold mt-4">CuadraMe está bloqueada</h1>
        <p className="text-sm text-ink-soft mt-1">Ingresa tu PIN para continuar</p>

        <div className="flex gap-3 mt-8 h-4" aria-label={`${pin.length} dígitos ingresados`}>
          {Array.from({ length: Math.max(4, pin.length) }).map((_, i) => (
            <span
              key={i}
              className={`w-3.5 h-3.5 rounded-full border-2 transition-colors ${
                i < pin.length ? 'bg-accent border-accent' : 'border-line'
              }`}
            />
          ))}
        </div>
        <p role="alert" className="text-xs text-danger mt-4 h-4">
          {espera > 0 ? `Espera ${espera} s para intentar de nuevo` : error}
        </p>

        <div className="grid grid-cols-3 gap-3 mt-6 w-full max-w-[280px]">
          {TECLAS.map((t) =>
            t === 'bio' && !bio ? (
              <span key={t} />
            ) : (
              <button
                key={t}
                type="button"
                onClick={() => tocar(t)}
                disabled={espera > 0}
                aria-label={t === 'borrar' ? 'Borrar' : t === 'bio' ? 'Usar huella o rostro' : t}
                className="h-16 rounded-2xl bg-paper-raised border border-line text-xl font-semibold flex items-center justify-center disabled:opacity-40"
              >
                {t === 'borrar' ? <Delete size={20} /> : t === 'bio' ? <Fingerprint size={22} className="text-accent" /> : t}
              </button>
            )
          )}
        </div>

        <button
          type="button"
          onClick={() => confirmar()}
          disabled={pin.length < 4 || verificando || espera > 0}
          className="w-full max-w-[280px] mt-5 bg-ink text-paper font-semibold rounded-2xl py-3.5 text-[15px] disabled:opacity-40"
        >
          Entrar
        </button>

        <button type="button" onClick={logout} className="mt-auto text-xs text-ink-soft underline">
          Olvidé mi PIN (cerrar sesión)
        </button>
      </div>
    </div>
  )
}
