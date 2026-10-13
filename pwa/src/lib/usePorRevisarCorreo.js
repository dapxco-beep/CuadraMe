import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

/**
 * Los movimientos que llegaron por el correo y esperan tu aprobación (GET /correos/pendientes),
 * ya ordenados por la fecha del movimiento. `quitar` los saca de la lista al aprobar o descartar
 * sin volver a pedir nada.
 */
export function usePorRevisarCorreo() {
  const [correos, setCorreos] = useState([])
  const [cargado, setCargado] = useState(false)
  const montado = useRef(true)

  const recargar = useCallback(async () => {
    try {
      const lista = await Promise.resolve(api.correosPendientes?.())
      if (montado.current) setCorreos(Array.isArray(lista) ? lista : [])
    } catch {
      /* sin conexión: se queda lo que había */
    } finally {
      if (montado.current) setCargado(true)
    }
  }, [])

  useEffect(() => {
    montado.current = true
    recargar()
    return () => {
      montado.current = false
    }
  }, [recargar])

  const quitar = useCallback((c) => setCorreos((prev) => prev.filter((x) => x.id !== c.id)), [])
  return { correos, cargado, recargar, quitar }
}
