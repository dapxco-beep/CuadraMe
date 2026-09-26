import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext'
import { api } from './api'

const CuentasContext = createContext(null)

export function CuentasProvider({ children }) {
  const { usuario } = useAuth()
  const [cuentas, setCuentas] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  const recargar = useCallback(async () => {
    if (!usuario) return
    setCargando(true)
    setError('')
    try {
      const cs = await api.cuentas()
      setCuentas(cs)
    } catch (err) {
      setError(err.message || 'No se pudieron cargar tus cuentas')
    } finally {
      setCargando(false)
    }
  }, [usuario])

  useEffect(() => {
    if (usuario) recargar()
  }, [usuario, recargar])

  return (
    <CuentasContext.Provider value={{ cuentas, cargando, error, recargar }}>
      {children}
    </CuentasContext.Provider>
  )
}

export function useCuentas() {
  return useContext(CuentasContext)
}
