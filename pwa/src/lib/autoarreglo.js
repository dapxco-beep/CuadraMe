// Autoarreglo: la app ordena sola las cuentas (ver docs/AUTOARREGLO.md). Aquí vive la lógica sin pantalla:
// el corredor (una sola vez por sesión y por hora, sin bloquear nada) y los textos, que siguen docs/GUIA_DE_TEXTOS.md.
import { useSyncExternalStore } from 'react'
import { api } from './api'
import { decisionVisible } from './decisionesAutoarreglo'

export const INTERVALO_MS = 60 * 60 * 1000 // una vez por hora (y una vez por sesión)
export const MAX_RONDAS = 12 // llamadas seguidas como mucho; lo que falte sigue en la próxima apertura
export const ESPERA_RONDAS_MS = 1200
const CLAVE_ULTIMA = 'cuadrame.autoarreglo.ultima'
const CLAVE_VISTO = 'cuadrame.autoarreglo.visto'

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`

function leer(clave) {
  try { return window.localStorage.getItem(clave) } catch { return null }
}
function guardar(clave, valor) {
  try { window.localStorage.setItem(clave, valor) } catch { /* sin almacenamiento: no pasa nada */ }
}

// ── Textos ─────────────────────────────────────────────────────────────────────────────────────
/** «Estoy ordenando tus cuentas… (2 de 6)». `hecho` = pasos ya terminados; el que va ahora es el siguiente. */
export function textoProgreso(progreso) {
  const total = progreso?.total || 6
  const actual = Math.min((progreso?.hecho || 0) + 1, total)
  return `Estoy ordenando tus cuentas… (${actual} de ${total})`
}

/** La frase del servidor ya viene lista («Listo, ordené tus cuentas: moví 4 extractos…»). */
export const textoListo = (resumen) => resumen?.texto || 'Listo, ordené tus cuentas.'

export { decisionVisible }

/** «Nu Colombia: de $2.700.000 a $2.706.100». */
export const textoSaldoCuenta = (c, fmt) => `${c.cuenta}: de ${fmt(c.saldo_antes)} a ${fmt(c.saldo_despues)}`

const ETIQUETA_DETALLE = {
  mover_cuenta: 'Pasado a tu tarjeta', corregir_tipo: 'Compra corregida', corregir_monto: 'Pago corregido',
  quitar_repetido: 'Repetido quitado', crear_linea: 'Movimiento agregado', ajuste_inicial: 'Saldo inicial',
}
export const etiquetaDetalle = (d) => ETIQUETA_DETALLE[d.tipo] || 'Cambio'

/** Líneas del conteo del lote para la hoja «Qué hice» (solo lo que no es cero). */
export function lineasConteo(c = {}) {
  const l = []
  if (c.extractos_movidos) l.push(`Pasé ${plural(c.extractos_movidos, 'extracto', 'extractos')} a tu tarjeta`)
  if (c.compras_corregidas) l.push(`Corregí ${plural(c.compras_corregidas, 'compra', 'compras')} que estaban como ingresos`)
  if (c.pagos_corregidos) l.push(`Corregí ${plural(c.pagos_corregidos, 'pago', 'pagos')} de tarjeta`)
  if (c.repetidos_quitados) l.push(`Quité ${plural(c.repetidos_quitados, 'movimiento repetido', 'movimientos repetidos')}`)
  if (c.rendimientos_registrados) l.push(`Registré ${plural(c.rendimientos_registrados, 'rendimiento o impuesto', 'rendimientos e impuestos')}`)
  if (c.lineas_importadas) l.push(`Traje ${plural(c.lineas_importadas, 'movimiento comprobado', 'movimientos comprobados')} de tus extractos`)
  if (c.ajustes_iniciales) l.push('Actualicé el saldo con el que empezaron tus cuentas')
  return l
}

// ── Corredor (una sola instancia para toda la app) ───────────────────────────────────────────────────
const REPOSO = { fase: 'reposo', progreso: null, resultado: null, decisiones: [], cuadre: [] }
let estado = REPOSO
let corriendo = null
let sesionIniciada = false
const oyentes = new Set()

function poner(parcial) {
  estado = { ...estado, ...parcial }
  oyentes.forEach((f) => f())
}

export const suscribir = (f) => { oyentes.add(f); return () => oyentes.delete(f) }
export const leerEstado = () => estado

/** Hook: el estado del autoarreglo para pintar el aviso. */
export function useAutoarreglo() {
  return useSyncExternalStore(suscribir, leerEstado, leerEstado)
}

export const esperar = (ms) => new Promise((r) => setTimeout(r, ms))

/** ¿Toca correr? Una vez por sesión y, pasada la primera, como mucho una vez por hora. */
export function tocaCorrer(ahora = Date.now()) {
  if (!sesionIniciada) return true
  const ultima = Number(leer(CLAVE_ULTIMA) || 0)
  return !ultima || ahora - ultima >= INTERVALO_MS
}

/** Lo marca como ya visto por la persona (no vuelve a salir el mismo lote). */
export function descartarAviso() {
  if (estado.resultado?.lote_id) guardar(CLAVE_VISTO, estado.resultado.lote_id)
  poner({ resultado: null, decisiones: [] })
}

/**
 * Corre el autoarreglo SIN bloquear la pantalla: llama al servidor tramo por tramo mientras diga 'trabajando'
 * (con una pausa corta) y publica el avance. Jamás lanza: si algo falla se calla y la app sigue normal.
 * Si ya hay uno corriendo devuelve ese mismo.
 */
export function iniciar({ forzar = false, espera = ESPERA_RONDAS_MS } = {}) {
  if (corriendo) return corriendo
  if (typeof api.correrAutoarreglo !== 'function') return Promise.resolve(estado) // cliente sin esta función (pruebas, versión vieja)
  if (!forzar && !tocaCorrer()) return Promise.resolve(estado)
  sesionIniciada = true
  corriendo = (async () => {
    try {
      let r = null
      for (let i = 0; i < MAX_RONDAS; i += 1) {
        r = await api.correrAutoarreglo()
        if (!r) break
        if (r.estado === 'trabajando') {
          poner({ fase: 'trabajando', progreso: r.progreso || { hecho: 0, total: 6 } })
          await esperar(espera)
          continue
        }
        break
      }
      guardar(CLAVE_ULTIMA, String(Date.now()))
      const resumen = r?.resumen
      const visible = resumen && resumen.cambios > 0 && !resumen.revertido && leer(CLAVE_VISTO) !== resumen.lote_id
      poner({
        fase: 'listo', progreso: null, resultado: visible ? resumen : null,
        decisiones: (r?.decisiones || []).map(decisionVisible), cuadre: r?.cuadre || [],
      })
      if (resumen?.cambios > 0 && typeof window !== 'undefined') window.dispatchEvent(new Event('cuadrame:movimientos-cambio'))
    } catch {
      poner({ fase: 'reposo', progreso: null }) // es un extra: si falla no se molesta a nadie
    } finally {
      corriendo = null
    }
    return estado
  })()
  return corriendo
}

/** Solo para pruebas. */
export function reiniciarParaPruebas() {
  estado = REPOSO
  corriendo = null
  sesionIniciada = false
  oyentes.clear()
  try { window.localStorage.removeItem(CLAVE_ULTIMA); window.localStorage.removeItem(CLAVE_VISTO) } catch { /* nada */ }
}
