import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext'
import { api } from './api'

const CategoriasContext = createContext(null)

export function CategoriasProvider({ children }) {
  const { usuario } = useAuth()
  const [categorias, setCategorias] = useState([])
  const [cargando, setCargando] = useState(true)
  const [subcategorias, setSubcategorias] = useState([]) // [{id, categoria, nombre, movimientos}]

  const recargar = useCallback(async () => {
    if (!usuario) return
    setCargando(true)
    try {
      // Siempre se piden TAMBIÉN las ocultas: la pantalla de Categorías las
      // necesita para poder reactivarlas, y los íconos de movimientos viejos
      // siguen resolviéndose aunque la categoría esté oculta. Los selectores
      // usan `nombres` / `activas`, que ya vienen filtrados.
      const cs = await api.categorias(true)
      setCategorias(cs)
      // Las subcategorías son opcionales: si fallan, todo sigue funcionando solo con categorías.
      try {
        const subs = await api.subcategorias?.()
        if (Array.isArray(subs)) setSubcategorias(subs)
      } catch {
        /* sin subcategorías */
      }
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

  const activas = categorias.filter((c) => c.activa)
  const nombres = activas.map((c) => c.nombre)
  // Para presupuestos: sin las categorías de sistema (intereses, 4x1000, rendimientos...), que no se presupuestan
  const nombresPresupuesto = activas.filter((c) => !c.es_sistema).map((c) => c.nombre)
  // nombre de categoría -> emoji, para mostrar el ícono real en listas y detalles
  const iconos = Object.fromEntries(categorias.map((c) => [c.nombre, c.icono]))
  const iconoDe = (nombre) => iconos[nombre] || '💳'
  const colores = Object.fromEntries(categorias.filter((c) => c.color).map((c) => [c.nombre, c.color]))
  const colorDe = (nombre) => colores[nombre] || null

  // Nombres que valen para un movimiento: 'expense' → categorías de gasto (y «ambos»), 'income' → de ingreso (y «ambos»).
  // Sin tipo (o 'transfer') salen todas. `incluir` fuerza una categoría ya asignada para que no desaparezca al editar.
  const nombresDe = (tipoMovimiento, incluir) => {
    const quiere = tipoMovimiento === 'income' ? 'ingreso' : tipoMovimiento === 'expense' ? 'gasto' : null
    const lista = activas.filter((c) => !quiere || !c.tipo || c.tipo === 'ambos' || c.tipo === quiere).map((c) => c.nombre)
    return incluir && !lista.includes(incluir) ? [incluir, ...lista] : lista
  }

  // Subcategorías de una categoría, en el orden en que se crearon
  const subsDe = (categoria) => subcategorias.filter((s) => s.categoria === categoria)

  return (
    <CategoriasContext.Provider
      value={{ categorias, activas, nombres, nombresDe, nombresPresupuesto, iconoDe, colorDe, cargando, recargar, subcategorias, subsDe }}
    >
      {children}
    </CategoriasContext.Provider>
  )
}

export function useCategorias() {
  return useContext(CategoriasContext)
}
