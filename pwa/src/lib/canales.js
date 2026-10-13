// Canales por los que puede llegar un mismo movimiento (regla central de duplicados del backend).
// «Registrado desde: atajo + correo + extracto» = qué canales lo confirmaron.

export const ETIQUETA_CANAL = {
  manual: 'app',
  atajo: 'atajo',
  correo: 'correo',
  extracto: 'extracto',
  importacion: 'archivo',
}

// Cómo se dice el canal en una frase («lo registraste desde el correo del banco»).
export const FRASE_CANAL = {
  manual: 'la app',
  atajo: 'el atajo',
  correo: 'el correo del banco',
  extracto: 'el extracto',
  importacion: 'un archivo',
}

const ORDEN = ['manual', 'atajo', 'correo', 'extracto', 'importacion']

// ['atajo', 'correo'] -> 'atajo + correo'. Ignora canales desconocidos; [] / null -> ''.
export function textoCanales(canales) {
  const lista = (canales || []).filter((c) => ETIQUETA_CANAL[c]).sort((a, b) => ORDEN.indexOf(a) - ORDEN.indexOf(b))
  return lista.map((c) => ETIQUETA_CANAL[c]).join(' + ')
}

// Texto de una lista de canales para una frase: 'el atajo y el correo del banco'.
export function fraseCanales(canales) {
  const lista = (canales || []).filter((c) => FRASE_CANAL[c]).sort((a, b) => ORDEN.indexOf(a) - ORDEN.indexOf(b))
  if (lista.length === 0) return ''
  const partes = lista.map((c) => FRASE_CANAL[c])
  return partes.length === 1 ? partes[0] : `${partes.slice(0, -1).join(', ')} y ${partes[partes.length - 1]}`
}

// ── Etiqueta de origen de cada movimiento y tarjeta ───────────────────────────────────────
// «correo», «extracto», «archivo», «a mano», «atajo». Si lo confirmaron varias vías, se dice cuáles:
// «confirmado por correo + extracto» (sin repetir la vía por la que nació).
export const ETIQUETA_ORIGEN = {
  manual: 'a mano',
  atajo: 'atajo',
  correo: 'correo',
  extracto: 'extracto',
  importacion: 'archivo',
  archivo: 'archivo',
}

export const etiquetaOrigen = (origen) => ETIQUETA_ORIGEN[origen] || ''

export function textoConfirmado(origen, canales) {
  const otros = (canales || []).filter((c) => c !== origen && ETIQUETA_ORIGEN[c])
    .sort((a, b) => ORDEN.indexOf(a) - ORDEN.indexOf(b))
  return otros.length >= 1 && (canales || []).length > 1 ? `confirmado por ${otros.map((c) => ETIQUETA_ORIGEN[c]).join(' + ')}` : ''
}

// Un movimiento que nació de una notificación del correo y aún no respalda un extracto es PROVISIONAL:
// «falta confirmar con el extracto». Solo se dice si el servidor mandó los canales (si no, no se afirma nada).
export const faltaConfirmarExtracto = (origen, canales) =>
  origen === 'correo' && Array.isArray(canales) && !canales.includes('extracto')
