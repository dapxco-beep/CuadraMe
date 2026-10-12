import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

// «Tu plata trabajando»: utilidades y un hook compartido. Todo lo que se muestra aquí es una
// ESTIMACIÓN (interés compuesto E.A.): la tasa y su fecha se muestran siempre junto a la cifra.

const EVENTO = 'cuadrame:rendimientos'

/** 0,10 -> «0,10 %»; 9 -> «9 %»; 9,25 -> «9,25 %». */
export function formatTasa(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '—'
  return `${Number(n).toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} %`
}

/** «2026-10-12» -> «12 oct 2026». */
export function fechaCorta(iso) {
  if (!iso) return ''
  const d = new Date(`${String(iso).slice(0, 10)}T12:00:00`)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).replace('.', '')
}

/** Lee la tasa que escribe la persona («9,5» o «9.5»); null si está vacía; NaN si no es un número válido. */
export function leerTasa(texto) {
  const t = String(texto ?? '').trim().replace('%', '').replace(',', '.')
  if (!t) return null
  const n = Number(t)
  return Number.isFinite(n) && n >= 0 && n <= 100 ? n : NaN
}

/** Avisa a todos los bloques de «Tu plata trabajando» que algo cambió (cajita, tasa, saldo). */
export function avisarCambioRendimientos() {
  window.dispatchEvent(new Event(EVENTO))
}

/** { datos, cargando, recargar }: el resumen de /rendimientos; falla en silencio (es un extra, nunca bloquea). */
let enVuelo = null // varias cuentas piden a la vez: una sola petición
export function useRendimientos() {
  const [datos, setDatos] = useState(null)
  const [cargando, setCargando] = useState(true)
  const cargar = useCallback(() => {
    if (!enVuelo) {
      enVuelo = Promise.resolve()
        .then(() => api.rendimientos?.())
        .catch(() => null)
        .finally(() => setTimeout(() => { enVuelo = null }, 0))
    }
    return enVuelo
      .then((r) => setDatos(r || null))
      .catch(() => {})
      .finally(() => setCargando(false))
  }, [])
  useEffect(() => {
    cargar()
    window.addEventListener(EVENTO, cargar)
    return () => window.removeEventListener(EVENTO, cargar)
  }, [cargar])
  return { datos, cargando, recargar: cargar }
}
