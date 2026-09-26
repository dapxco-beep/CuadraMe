import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from './supabase'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setCargando(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s)
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

  const usuario = session
    ? {
        id: session.user.id,
        email: session.user.email,
        nombre: session.user.user_metadata?.nombre || session.user.email.split('@')[0],
      }
    : null

  return (
    <AuthContext.Provider value={{ usuario, session, cargando, login, registro, loginConGoogle, logout }}>
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
  if (msg.includes('Password should be at least')) return 'La contraseña debe tener al menos 6 caracteres'
  return msg
}
