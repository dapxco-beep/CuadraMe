// Saca el nombre del comercio de una descripción bancaria, igual que el backend
// (autocat.patron_de_comercio): 'Compra en JUAN VALDEZ SKANDIA con tarjeta débito'
// -> 'JUAN VALDEZ SKANDIA'. Se muestra editable antes de crear la regla.
const PREFIJOS =
  /^\s*(compra|pago|retiro|abono|cargo|transferencia|consignacion|consignación|debito|débito)(\s+(en|a|de|por|desde|pse|nequi|tarjeta|tc|td))*\s+/i
const CORTES = /\s+(con\s+tarjeta|con\s+tc|con\s+td|tarjeta|ref\b|nro\b|no\.|#|cuenta\b|cta\b|\d{3,})/i

export function patronDeComercio(descripcion) {
  const texto = (descripcion || '').trim()
  let resto = texto.replace(PREFIJOS, '')
  const m = CORTES.exec(resto)
  if (m) resto = resto.slice(0, m.index)
  let patron = resto.replace(/\s+/g, ' ').replace(/^[\s\-*.,:]+|[\s\-*.,:]+$/g, '')
  if (patron.length < 2) patron = texto.replace(/\s+/g, ' ')
  return patron.slice(0, 60)
}

export const RAZON_AUTO = {
  regla: 'por tu regla',
  comercio: 'por comercio conocido',
  similar: 'similar a movimientos tuyos',
  sugerida: 'sugerida por tu correo',
}

// Un movimiento "espera revisión" si la app lo categorizó sola sin confirmar,
// o si quedó en 'Otros' (los traslados propios no cuentan).
export function esAuto(m) {
  return m.cat_confirmada === false
}
export function porRevisar(m) {
  return m.fuente !== 'transferencia_interna' && (esAuto(m) || m.categoria === 'Otros')
}
