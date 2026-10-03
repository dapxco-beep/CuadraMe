import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from './supabase'

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

  async function loginConGoogle() {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
    if (error) throw new Error(traducirError(error.message))
  }

  async function logout() {
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
        nombre: session.user.user_metadata?.nombre || session.user.email.split('@')[0],
      }
    : null

  return (
    <AuthContext.Provider value={{ usuario, session, cargando, recuperando, login, registro, loginConGoogle, logout, recuperarPassword, cambiarPassword }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

function traducirError(msg) {
  if (msg.includes('Invalid login credentials')) return 'Correo o contraseña incorrectos'
  if (msg.includes('User already registered')) return 'Ese correo ya está registrado'
  if (msg.includes('Password should be at least')) return 'La contraseña es muy corta'
  if (msg.includes('Email not confirmed')) return 'Confirma tu correo antes de entrar (revisa tu bandeja y spam)'
  if (msg.includes('rate limit') || msg.includes('too many')) return 'Demasiados intentos. Espera unos minutos e intenta de nuevo'
  if (msg.includes('same password')) return 'La nueva contraseña debe ser distinta a la anterior'
  if (msg.includes('Failed to fetch')) return 'Sin conexión. Revisa tu internet e intenta de nuevo'
  return msg
}
