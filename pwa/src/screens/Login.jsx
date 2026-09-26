import { useState } from 'react'
import { useAuth } from '../lib/AuthContext'

export default function Login() {
  const { login, registro, loginConGoogle } = useAuth()
  const [modo, setModo] = useState('login') // login | registro
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [cargando, setCargando] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setMensaje('')
    setCargando(true)
    try {
      if (modo === 'login') {
        await login(email, password)
      } else {
        await registro(nombre, email, password)
        setMensaje('Revisa tu correo para confirmar tu cuenta antes de entrar')
      }
    } catch (err) {
      setError(err.message || 'Algo salió mal')
    } finally {
      setCargando(false)
    }
  }

  async function onGoogle() {
    setError('')
    try {
      await loginConGoogle()
    } catch (err) {
      setError(err.message || 'No se pudo iniciar con Google')
    }
  }

  return (
    <div className="flex-1 flex flex-col justify-center px-8 py-10">
      <div className="text-center mb-8">
        <div className="w-16 h-16 rounded-3xl bg-accent mx-auto mb-4" />
        <h1 className="text-2xl font-bold">CuadraMe</h1>
        <p className="text-sm text-ink-soft mt-1">Cuadra tus cuentas, simple y al día</p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        {modo === 'registro' && (
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Nombre"
            required
            className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
          />
        )}
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          type="email"
          placeholder="Correo"
          required
          className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
        />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          placeholder="Contraseña"
          required
          minLength={6}
          className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
        />

        {error && <p className="text-sm text-danger">{error}</p>}
        {mensaje && <p className="text-sm text-accent">{mensaje}</p>}

        <button
          type="submit"
          disabled={cargando}
          className="mt-2 w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] active:scale-[0.98] transition-transform disabled:opacity-60"
        >
          {cargando ? 'Un momento...' : modo === 'login' ? 'Entrar' : 'Crear cuenta'}
        </button>
      </form>

      <div className="flex items-center gap-3 my-5">
        <div className="flex-1 h-px bg-line" />
        <span className="text-xs text-ink-soft">o</span>
        <div className="flex-1 h-px bg-line" />
      </div>

      <button
        onClick={onGoogle}
        className="w-full flex items-center justify-center gap-2 rounded-2xl border border-line bg-paper-raised py-3.5 text-sm font-semibold"
      >
        <GoogleIcon /> Continuar con Google
      </button>

      <button
        onClick={() => setModo(modo === 'login' ? 'registro' : 'login')}
        className="text-sm text-accent font-medium mt-5 text-center"
      >
        {modo === 'login' ? '¿No tienes cuenta? Regístrate' : '¿Ya tienes cuenta? Inicia sesión'}
      </button>
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 01-1.8 2.72v2.26h2.9c1.7-1.57 2.7-3.88 2.7-6.62z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.8.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33A9 9 0 009 18z" />
      <path fill="#FBBC05" d="M3.95 10.7A5.4 5.4 0 013.68 9c0-.59.1-1.17.27-1.7V4.97H.96A9 9 0 000 9c0 1.45.35 2.83.96 4.03l2.99-2.33z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 00.96 4.97l2.99 2.33C4.66 5.17 6.65 3.58 9 3.58z" />
    </svg>
  )
}
