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
