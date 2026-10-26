import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import { EncabezadoMarca } from '../brand/Marca'
import { mensajeDeError } from '../lib/mensajes'

export default function Login() {
  const { login, registro, confirmarCodigo, reenviarCodigo, loginConGoogle, recuperarPassword } = useAuth()
  const [modo, setModo] = useState('login') // login | registro
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [aceptaTerminos, setAceptaTerminos] = useState(false)
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [cargando, setCargando] = useState(false)
  const [esperaCodigo, setEsperaCodigo] = useState(false) // tras crear la cuenta: escribe el código que llegó al correo
  const [codigo, setCodigo] = useState('')

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setMensaje('')

    if (modo === 'registro' && !aceptaTerminos) {
      setError('Debes aceptar los Términos y la Política de Privacidad para continuar')
      return
    }

    setCargando(true)
    try {
      if (modo === 'login') {
        await login(email, password)
      } else {
        await registro(nombre, email, password)
        setEsperaCodigo(true)
        setMensaje(`Te enviamos un correo a ${email.trim()}. Escribe aquí el código que trae, o toca el enlace del correo. Revisa también el spam.`)
      }
    } catch (err) {
      setError(mensajeDeError(err, 'No pudimos continuar. Intenta de nuevo.'))
    } finally {
      setCargando(false)
    }
  }

  async function onConfirmar(e) {
    e.preventDefault()
    setError('')
    setCargando(true)
    try {
      await confirmarCodigo(email.trim(), codigo)
      // al acertar, la sesión se abre sola y la app te lleva adentro
    } catch (err) {
      setError(mensajeDeError(err, 'No pudimos confirmar el código. Intenta de nuevo.'))
    } finally {
      setCargando(false)
    }
  }

  async function onReenviar() {
    setError('')
    try {
      await reenviarCodigo(email.trim())
      setMensaje('Listo, te enviamos un código nuevo.')
    } catch (err) {
      setError(mensajeDeError(err, 'No pudimos reenviar el código. Intenta en unos minutos.'))
    }
  }

  async function onOlvide() {
    setError('')
    setMensaje('')
    if (!email.trim()) return setError('Escribe tu correo arriba y vuelve a tocar "¿Olvidaste tu contraseña?"')
    try {
      await recuperarPassword(email.trim())
      // Mismo mensaje exista o no el correo, para no revelar quién tiene cuenta.
      setMensaje('Si ese correo tiene cuenta, te enviamos un enlace para crear una contraseña nueva')
    } catch (err) {
      setError(mensajeDeError(err, 'No pudimos enviar el correo. Intenta de nuevo.'))
    }
  }

  async function onGoogle() {
    setError('')
    if (modo === 'registro' && !aceptaTerminos) {
      setError('Debes aceptar los Términos y la Política de Privacidad para continuar')
      return
    }
    try {
      await loginConGoogle()
    } catch (err) {
      setError(mensajeDeError(err, 'No pudimos entrar con Google. Intenta de nuevo.'))
    }
  }

  if (esperaCodigo) {
    return (
      <div className="flex-1 flex flex-col justify-center px-8 py-10 pantalla-centrada">
        <EncabezadoMarca titulo="Confirma tu correo" />
        <form onSubmit={onConfirmar} className="flex flex-col gap-3" data-testid="paso-codigo">
          <input
            value={codigo}
            onChange={(e) => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 8))}
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="Código del correo"
            aria-label="Código del correo"
            required
            minLength={6}
            className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-center text-xl tracking-[0.3em] outline-none focus:border-accent"
          />
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
          {mensaje && <p role="status" className="text-sm text-accent">{mensaje}</p>}
          <button
            type="submit"
            disabled={cargando || codigo.length < 6}
            className="mt-2 w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] active:scale-[0.98] transition-transform disabled:opacity-50"
          >
            {cargando ? 'Un momento...' : 'Confirmar y entrar'}
          </button>
                    <button type="button" onClick={onReenviar} className="text-sm text-accent font-medium text-center min-h-11">
            Reenviar código
          </button>
          <button
            type="button"
            onClick={() => { setEsperaCodigo(false); setCodigo(''); setError(''); setMensaje('') }}
            className="text-xs text-ink-soft text-center min-h-11"
          >
            Cambiar el correo
          </button>
        </form>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col justify-center px-8 py-10 pantalla-centrada">
      <EncabezadoMarca titulo={modo === 'login' ? 'CuadraMe — inicia sesión' : 'CuadraMe — crea tu cuenta'} />

      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        {modo === 'registro' && (
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Nombre"
            aria-label="Nombre"
            autoComplete="name"
            required
            className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
          />
        )}
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          type="email"
          placeholder="Correo"
          aria-label="Correo"
          autoComplete="email"
          required
          className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
        />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          placeholder="Contraseña"
          required
          minLength={modo === 'registro' ? 8 : 6}
          autoComplete={modo === 'registro' ? 'new-password' : 'current-password'}
          aria-label="Contraseña"
          className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
        />

        {modo === 'login' && (
          <button type="button" onClick={onOlvide} className="text-xs text-accent font-medium text-right -mt-1">
            ¿Olvidaste tu contraseña?
          </button>
        )}

        {modo === 'registro' && (
          <label className="flex items-start gap-2.5 px-1">
            <input
              type="checkbox"
              checked={aceptaTerminos}
              onChange={(e) => setAceptaTerminos(e.target.checked)}
              className="mt-0.5 w-4 h-4 shrink-0 accent-accent"
            />
            <span className="text-xs text-ink-soft leading-relaxed">
              Acepto los{' '}
              <Link to="/legal/terminos" className="text-accent font-medium">Términos y Condiciones</Link>,
              la{' '}
              <Link to="/legal/privacidad" className="text-accent font-medium">Política de Privacidad</Link>
              {' '}y la{' '}
              <Link to="/legal/autorizacion-datos" className="text-accent font-medium">Autorización de tratamiento de datos</Link>.
            </span>
          </label>
        )}

        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        {mensaje && <p role="status" className="text-sm text-accent">{mensaje}</p>}

        <button
          type="submit"
          disabled={cargando || (modo === 'registro' && !aceptaTerminos)}
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
        disabled={modo === 'registro' && !aceptaTerminos}
        className="w-full flex items-center justify-center gap-2 rounded-2xl border border-line bg-paper-raised py-3.5 text-sm font-semibold disabled:opacity-50"
      >
        <GoogleIcon /> Continuar con Google
      </button>
      {modo === 'login' && (
        <p className="text-[11px] text-ink-soft text-center mt-2 leading-relaxed">
          Si es tu primera vez, al continuar aceptas los{' '}
          <Link to="/legal/terminos" className="text-accent">Términos</Link> y la{' '}
          <Link to="/legal/privacidad" className="text-accent">Política de Privacidad</Link>{' '}
          (<a href="/privacidad.html" className="text-accent">versión pública</a>).
        </p>
      )}

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
