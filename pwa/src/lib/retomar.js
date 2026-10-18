// Conciliación retomable: qué extractos quedaron a medias, cómo se dicen y el borrador de la revisión.
// Puro (sin React) para probarlo fácil. El servidor ya manda cada extracto con su estado
// (`todos_extractos.items`): aquí solo se escogen los que están «por revisar» y tienen una revisión guardada.

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`

/** Extractos con revisión guardada a los que aún les faltan movimientos por importar. */
export function extractosAMedias(estado) {
  const items = estado?.todos_extractos?.items || estado?.extractos || []
  return items
    .filter((x) => x?.historial_id && (x.estado_vista === 'por_revisar' || x.estado === 'por_revisar') && Number(x.por_revisar) > 0)
    .map((x) => ({
      historialId: x.historial_id,
      cuentaId: x.cuenta_id || '',
      cuenta: x.cuenta || x.banco || 'Cuenta',
      mes: x.mes_etiqueta || '',
      faltan: Number(x.por_revisar),
      sugerencia: x.puede_cambiar_cuenta ? x.sugerencia_cuenta || null : null,
      // Qué extracto es de verdad («Tarjeta Nu · corte 15 oct 2026») y de dónde salió: nada sin nombre ni origen.
      titulo: x.titulo || '',
      origen: x.origen_texto || '',
    }))
}

export const tituloAMedias = (n) => (n === 1 ? 'Tienes 1 extracto a medio conciliar' : `Tienes ${n} extractos a medio conciliar`)
export const textoFaltan = (n) => `faltan importar ${plural(n, 'movimiento', 'movimientos')}`

/** «Subiste 6: 3 conciliados, 2 por importar, 1 sin clave» a partir de lo que pasó con cada archivo. */
export function resumenLote(archivos) {
  const total = archivos.length
  if (total < 2) return ''
  let conciliados = 0
  let porImportar = 0
  let sinClave = 0
  let conError = 0
  for (const a of archivos) {
    if (a.estado === 'falta_clave') sinClave++
    else if (a.estado === 'error') conError++
    else if (a.estado === 'listo') {
      const faltan = (a.items || []).filter((it) => it.estado === 'nuevo' || it.estado === 'posible').length
      if (faltan > 0) porImportar++
      else conciliados++
    }
  }
  const partes = []
  if (conciliados) partes.push(`${conciliados} ${conciliados === 1 ? 'conciliado' : 'conciliados'}`)
  if (porImportar) partes.push(`${porImportar} por importar`)
  if (sinClave) partes.push(`${sinClave} sin clave`)
  if (conError) partes.push(`${conError} con error`)
  return `Subiste ${total}: ${partes.join(', ')}`
}

// ── Borrador de la revisión (sobrevive a salir y volver; vive solo en esta pestaña) ──────────
const clave = (historialId) => `cuadrame:borrador-revision:${historialId}`

export function guardarBorrador(historialId, { seleccion, categorias, aprender, titulos = {}, recordarTitulo = {}, montos = {} }) {
  if (!historialId) return
  try {
    sessionStorage.setItem(clave(historialId), JSON.stringify({ seleccion: [...seleccion], categorias, aprender, titulos, recordarTitulo, montos }))
  } catch { /* sin almacenamiento: se sigue sin borrador */ }
}

export function leerBorrador(historialId) {
  if (!historialId) return null
  try {
    const b = JSON.parse(sessionStorage.getItem(clave(historialId)) || 'null')
    return b && typeof b === 'object' ? { seleccion: new Set(b.seleccion || []), categorias: b.categorias || {}, aprender: b.aprender || {}, titulos: b.titulos || {}, recordarTitulo: b.recordarTitulo || {}, montos: b.montos || {} } : null
  } catch {
    return null
  }
}

export function borrarBorrador(historialId) {
  try {
    sessionStorage.removeItem(clave(historialId))
  } catch { /* nada */ }
}
