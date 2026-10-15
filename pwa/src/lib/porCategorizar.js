// Lógica pura de «Por categorizar» (sin React): selección por movimiento y por comercio, textos y
// qué comercios entran en «lo que más pesa». El servidor decide QUÉ es pendiente
// (backend/app/pendientes.py); aquí solo se maneja lo que el usuario elige.

export const LIMITE_VISIBLE = 10 // «Los 10 que más pesan»
export const LIMITE_RAPIDO = 7 // «Categorizar lo que más pesa en 1 minuto»

export const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`

/** Selección = conjunto de huellas (comercios completos) + ids sueltos. Inmutable. */
export const SELECCION_VACIA = { huellas: new Set(), ids: new Set() }

export function alternarComercio(sel, huella) {
  const huellas = new Set(sel.huellas)
  const ids = new Set(sel.ids)
  if (huellas.has(huella)) huellas.delete(huella)
  else huellas.add(huella)
  return { huellas, ids }
}

export function alternarMovimiento(sel, id) {
  const ids = new Set(sel.ids)
  if (ids.has(id)) ids.delete(id)
  else ids.add(id)
  return { huellas: new Set(sel.huellas), ids }
}

/** «Seleccionar los visibles». */
export function seleccionarVisibles(grupos) {
  return { huellas: new Set(grupos.map((g) => g.huella)), ids: new Set() }
}

/** «Los N de este comercio»: todo el comercio queda marcado. */
export function seleccionarComercio(sel, huella) {
  const huellas = new Set(sel.huellas)
  huellas.add(huella)
  return { huellas, ids: new Set(sel.ids) }
}

export const ninguno = () => ({ huellas: new Set(), ids: new Set() })

/** Cuántos movimientos abarca la selección (sin contar dos veces un movimiento suelto de un comercio ya marcado). */
export function contarSeleccion(sel, grupos) {
  let n = 0
  for (const g of grupos) {
    if (sel.huellas.has(g.huella)) n += g.conteo
    else n += (g.movimiento_ids || []).filter((id) => sel.ids.has(id)).length
  }
  return n
}

export const hayAlgo = (sel) => sel.huellas.size + sel.ids.size > 0

/** Cuerpo para POST /por-categorizar/accion a partir de la selección. */
export function cuerpoAccion(accion, sel, extra = {}) {
  return { accion, huellas: [...sel.huellas], movimiento_ids: [...sel.ids], ...extra }
}

/** Los comercios del «1 minuto»: los relevantes primero (ya vienen por impacto); si no hay, los de más monto. */
export function loQueMasPesa(grupos, max = LIMITE_RAPIDO) {
  const rel = grupos.filter((g) => g.relevante)
  return (rel.length ? rel : grupos).slice(0, max)
}

/** Texto del aviso al terminar una acción, para el «Deshacer». */
export function textoResultado(accion, r) {
  const n = r?.movimientos || 0
  if (accion === 'categoria') return `Listo: ${plural(n, 'movimiento categorizado', 'movimientos categorizados')}.`
  if (accion === 'dejar') return `Dejé ${plural(n, 'movimiento', 'movimientos')} como estaban.`
  if (accion === 'marcar') return `Marqué ${plural(n, 'movimiento', 'movimientos')} para revisar.`
  const c = r?.huellas?.length || 0
  if (accion === 'no_preguntar') return `No te volveré a preguntar por ${plural(c, 'comercio', 'comercios')}.`
  return `Oculté ${plural(c, 'comercio', 'comercios')} de esta lista.`
}

/** «Recordar para este comercio» viene activado solo si el comercio se repite 4 o más veces (más de 3). */
export const MIN_REPETICIONES_RECORDAR = 4
export const recordarPorDefecto = (repeticiones) => (repeticiones || 0) >= MIN_REPETICIONES_RECORDAR

/** Vista previa de la regla: «afectará 12 movimientos pasados y los futuros». */
export function textoVistaPrevia(pasados) {
  if (!pasados) return 'Afectará los próximos movimientos de este comercio.'
  return `Afectará ${plural(pasados, 'movimiento pasado', 'movimientos pasados')} y los futuros.`
}
