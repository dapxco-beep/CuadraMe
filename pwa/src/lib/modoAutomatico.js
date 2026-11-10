// Modo automático: un solo interruptor (Perfil) que deja a la app resolver sola lo SEGURO (correos de tu banco, «¿son tuyos?»,
// diferencias de centavos, «¿es el mismo gasto?» con monto igual). Activado por defecto en el servidor; apagado, todo
// se comporta como antes. Aquí vive la lectura/escritura del ajuste y la regla pura del «mismo gasto».
import { useEffect, useState } from 'react'
import { api } from './api'

export const DIAS_MISMO_GASTO = 3
let cache = null // null = aún no se sabe

/** ¿Está activado? Sin saberlo (sin red o cliente viejo) se responde false: ante la duda la app pregunta como siempre. */
export async function cargarModoAutomatico() {
  if (typeof api.modoAutomatico !== 'function') return false
  try {
    const r = await api.modoAutomatico()
    cache = r?.activo !== false
  } catch {
    cache = false
  }
  return cache
}

export function useModoAutomatico() {
  const [activo, setActivo] = useState(cache)
  useEffect(() => {
    let vivo = true
    cargarModoAutomatico().then((v) => { if (vivo) setActivo(v) })
    return () => { vivo = false }
  }, [])
  async function cambiar(valor) {
    const anterior = activo
    setActivo(valor)
    try {
      const r = await api.guardarModoAutomatico(valor)
      cache = r?.activo !== false
      setActivo(cache)
    } catch (err) {
      setActivo(anterior)
      throw err
    }
  }
  return { activo, cambiar }
}

const dia = (t) => {
  const d = new Date(`${String(t || '').slice(0, 10)}T00:00:00`)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * «¿Es el mismo gasto?» se resuelve sin preguntar SOLO si: el monto es idéntico (diferencia < 1), hay ≤ 3 días entre las
 * fechas y el movimiento que ya tenías no lo reclama otra línea (1:1). Con otro monto, o con dudas, se pregunta.
 * `it` = línea dudosa; `todas` = las dudosas del mismo archivo.
 */
export function esMismoGastoSeguro(it, todas = []) {
  if (!it || it.estado !== 'dudoso' || it.noAuto || it.dudosa || !it.registrado || !it.matchId) return false
  const monto = Number(it.monto)
  const registrado = Number(it.registrado.monto)
  if (!(monto >= 1) || !Number.isFinite(registrado) || Math.abs(monto - registrado) >= 1) return false
  const a = dia(it.fecha)
  const b = dia(it.registrado.fecha)
  if (!a || !b || Math.abs(a - b) / 86400000 > DIAS_MISMO_GASTO) return false
  const reclaman = todas.filter((o) => o.estado === 'dudoso' && o.matchId === it.matchId)
  return reclaman.length === 1
}
