import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext'
import { api } from './api'

const CategoriasContext = createContext(null)

export function CategoriasProvider({ children }) {
  const { usuario } = useAuth()
  const [categorias, setCategorias] = useState([])
  const [cargando, setCargando] = useState(true)

  const recargar = useCallback(async () => {
    if (!usuario) return
    setCargando(true)
    try {
      const cs = await api.categorias()
      setCategorias(cs)
    } catch {
      // si falla, se sigue usando lo que ya había en memoria — las pantallas
      // que dependen de esto (Agregar, Presupuesto...) no deben bloquearse
      // por un fallo de red al listar categorías.
    } finally {
      setCargando(false)
    }
  }, [usuario])

  useEffect(() => {
    if (usuario) recargar()
  }, [usuario, recargar])

  const nombres = categorias.map((c) => c.nombre)
  // nombre de categoría -> emoji, para mostrar el ícono real en listas y detalles
  const iconos = Object.fromEntries(categorias.map((c) => [c.nombre, c.icono]))
  const iconoDe = (nombre) => iconos[nombre] || '💳'

  return (
    <CategoriasContext.Provider value={{ categorias, nombres, iconoDe, cargando, recargar }}>
      {children}
    </CategoriasContext.Provider>
  )
}

export function useCategorias() {
  return useContext(CategoriasContext)
}
