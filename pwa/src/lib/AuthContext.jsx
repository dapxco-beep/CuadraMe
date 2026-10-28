import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from './supabase'
import { borrarSeguridad } from './seguridad'
import { olvidarVistos } from './ultimoVisto'
import { vaciarCola } from './colaOffline'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [cargando, setCargando] = useState(true)
  // true cuando el usuario llegó desde el enlace "restablecer contraseña" del correo
  const [recuperando, setRecuperando] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setCargando(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((evento, s) => {
      setSession(s)
      if (evento === 'SIGNED_OUT') olvidarVistos()
      if (evento === 'PASSWORD_RECOVERY') setRecuperando(true)
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  async function login(email, password) {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw new Error(traducirError(error.message))
  }

  async function registro(nombre, email, password) {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { nombre } },
    })
    if (error) throw new Error(traducirError(error.message))
  }

  // Confirmar el correo con el código que llega por email (en vez de abrir un enlace): al acertar, entra solo.
  async function confirmarCodigo(email, codigo) {
    const { error } = await supabase.auth.verifyOtp({ email, token: String(codigo).trim(), type: 'signup' })
    if (error) throw new Error(traducirError(error.message))
  }

  async function reenviarCodigo(email) {
    const { error } = await supabase.auth.resend({ type: 'signup', email })
    if (error) throw new Error(traducirError(error.message))
  }

  async function loginConGoogle() {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
    if (error) throw new Error(traducirError(error.message))
  }

  async function logout() {
    // El PIN y la huella son de este dispositivo y de esta sesión: se borran
    // ANTES de salir para que, pase lo que pase con la red, no queden atrás.
    borrarSeguridad()
    olvidarVistos()
    vaciarCola()
    await supabase.auth.signOut()
  }

  async function recuperarPassword(email) {
    const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: window.location.origin })
    if (error) throw new Error(traducirError(error.message))
  }

  async function cambiarPassword(nueva) {
    const { error } = await supabase.auth.updateUser({ password: nueva })
    if (error) throw new Error(traducirError(error.message))
    setRecuperando(false)
  }

  const usuario = session
    ? {
        id: session.user.id,
        email: session.user.email,
        // Sin inventar: el correo no es un nombre. Si no hay, queda vacío y la app se lee bien sin él.
        nombre:
          session.user.user_metadata?.nombre ||
          session.user.user_metadata?.full_name ||
          session.user.user_metadata?.name ||
          '',
        nombrePila: session.user.user_metadata?.given_name || '',
      }
    : null

  return (
    <AuthContext.Provider value={{ usuario, session, cargando, recuperando, login, registro, confirmarCodigo, reenviarCodigo, loginConGoogle, logout, recuperarPassword, cambiarPassword }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

export function traducirError(texto) {
  const msg = String(texto || '')
  if (msg.includes('Invalid login credentials')) return 'Correo o contraseña incorrectos'
  if (msg.includes('User already registered')) return 'Ese correo ya está registrado'
  if (msg.includes('Password should be at least')) return 'La contraseña es muy corta'
  if (msg.includes('Email not confirmed')) return 'Confirma tu correo antes de entrar (revisa tu bandeja y spam)'
  if (msg.includes('rate limit') || msg.includes('too many')) return 'Demasiados intentos. Espera unos minutos e intenta de nuevo'
  if (msg.includes('same password')) return 'La nueva contraseña debe ser distinta a la anterior'
  if (/email address.*invalid|invalid.*email|unable to validate email/i.test(msg)) return 'Ese correo no parece válido. Revísalo e intenta de nuevo'
  if (msg.includes('Token has expired') || /otp.*(invalid|expired)|invalid.*(token|otp|code)/i.test(msg)) return 'El código no es correcto o ya venció. Revisa los números o pide uno nuevo'
  if (/invalid/i.test(msg)) return 'Algo de lo que escribiste no es válido. Revísalo e intenta de nuevo'
  if (msg.includes('sending') || msg.includes('not authorized')) return 'No pudimos enviar el correo ahora. Intenta de nuevo en unos minutos'
  if (msg.includes('Failed to fetch')) return 'Sin conexión. Revisa tu internet e intenta de nuevo'
  return msg
}
