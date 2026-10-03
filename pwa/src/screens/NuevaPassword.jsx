import { useState } from 'react'
import { useAuth } from '../lib/AuthContext'

// Se muestra cuando el usuario entra desde el enlace "restablecer contraseña"
// del correo: Supabase ya lo dejó con sesión, solo falta que escriba la nueva.
export default function NuevaPassword() {
  const { cambiarPassword } = useAuth()
  const [password, setPassword] = useState('')
  const [confirmar, setConfirmar] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 8) return setError('Usa al menos 8 caracteres')
    if (password !== confirmar) return setError('Las contraseñas no coinciden')
    setCargando(true)
    try {
      await cambiarPassword(password)
    } catch (err) {
      setError(err.message || 'No se pudo cambiar la contraseña')
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col justify-center px-8 py-10">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold">Crea una contraseña nueva</h1>
        <p className="text-sm text-ink-soft mt-1">Después de guardarla entras directo a tu cuenta</p>
      </div>
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Nueva contraseña (mín. 8 caracteres)"
          autoComplete="new-password"
          aria-label="Nueva contraseña"
          required
          className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
        />
        <input
          type="password"
          value={confirmar}
          onChange={(e) => setConfirmar(e.target.value)}
          placeholder="Repite la contraseña"
          autoComplete="new-password"
          aria-label="Repite la contraseña"
          required
          className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
        />
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <button
          type="submit"
          disabled={cargando}
          className="mt-2 w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {cargando ? 'Guardando...' : 'Guardar contraseña'}
        </button>
      </form>
    </div>
  )
}
