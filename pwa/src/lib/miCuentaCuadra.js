// «Mi cuenta cuadra»: lo que el autoarreglo dejó por cuenta (campo `cuadre` de POST /autoarreglo/correr) convertido a un
// semáforo que se entiende solo. Puro y probado en test/mi_cuenta_cuadra.test.js. Textos según docs/GUIA_DE_TEXTOS.md.
import { nombreMes } from './sincronizacion'

export const RUTA_DETALLE = '/sincronizacion#cuadre'
const MAX_CAUSA = 120

/** Primera frase de `causa`, recortada con «…» si es larga. */
export function unaFrase(texto, max = MAX_CAUSA) {
  const t = String(texto || '').replace(/\s+/g, ' ').trim()
  if (!t) return ''
  const m = t.match(/^.*?[.!?](?=\s|$)/)
  const frase = m ? m[0] : t
  return frase.length <= max ? frase : `${frase.slice(0, max - 1).replace(/[\s,;:.]+$/, '')}…`
}

const mayus = (t) => (t ? t[0].toUpperCase() + t.slice(1) : t)

/**
 * Una cuenta del servidor lista para pintar:
 * { id, nombre, estado: 'cuadra'|'no_cuadra', titulo, detalle, ruta }.
 * Verde: «Cuadra todos los meses» (con «Solo falta el extracto de …» si el servidor lo dice).
 * Ámbar: el mes en que deja de cuadrar y el motivo en una frase.
 */
export function vistaCuadre(c) {
  const ruta = c?.ruta || RUTA_DETALLE
  const base = { id: c?.cuenta_id, nombre: c?.cuenta || 'Cuenta', ruta }
  if (c?.estado === 'no_cuadra') {
    const mes = nombreMes(c.primer_mes_malo)
    return {
      ...base, estado: 'no_cuadra',
      titulo: mes ? `Deja de cuadrar en ${mes}` : 'No cuadra',
      detalle: unaFrase(c.causa) || unaFrase(c.texto),
    }
  }
  const resto = String(c?.texto || '').split(';')[1]
  return { ...base, estado: 'cuadra', titulo: 'Cuadra todos los meses', detalle: resto ? mayus(resto.trim()) : '' }
}

/** Las que no cuadran primero (lo que pide atención), luego las verdes; dentro de cada grupo, el orden del servidor. */
export function vistasCuadre(cuadre) {
  const v = (Array.isArray(cuadre) ? cuadre : []).map(vistaCuadre)
  return [...v.filter((x) => x.estado === 'no_cuadra'), ...v.filter((x) => x.estado === 'cuadra')]
}

/** «Todas tus cuentas cuadran» / «2 de 3 cuentas cuadran» / «Ninguna cuenta cuadra todavía». */
export function resumenCuadre(vistas) {
  const n = vistas.length
  if (!n) return ''
  const ok = vistas.filter((v) => v.estado === 'cuadra').length
  if (ok === n) return n === 1 ? 'Tu cuenta cuadra todos los meses' : 'Todas tus cuentas cuadran'
  if (ok === 0) return n === 1 ? 'Una cuenta necesita tu revisión' : 'Ninguna cuenta cuadra todavía'
  return `${ok} de ${n} cuentas cuadran`
}
