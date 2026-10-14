// Textos y reglas puras del modelo de estados de «Traer movimientos» (el backend lo calcula en
// app/estado_traer.py; aquí solo se dice en palabras). Sin React, fáciles de probar.

// Botón principal de cada tarjeta de «Por hacer» (una acción por tarjeta, verbo primero).
export const BOTON_TAREA = {
  correos_por_revisar: 'Ver los por revisar',
  falta_clave: 'Poner la clave',
  extractos_por_conciliar: 'Conciliar',
  extractos_sin_leer: 'Subir de nuevo',
  posibles_duplicados: 'Ver los repetidos',
  sin_cuenta: 'Crear la cuenta',
  movimientos_por_categorizar: 'Poner categorías',
  movimientos_por_confirmar: 'Confirmar si son tuyos',
}

// Extractos que ya no piden nada: van en «Al día». Los demás piden acción (arriba, en «Por hacer»).
export const ESTADOS_AL_DIA = ['al_dia', 'sin_movimientos_reales', 'anterior_al_inicio']

export const separarEstados = (extractos) => {
  const lista = Array.isArray(extractos) ? extractos : []
  return { alDia: lista.filter((x) => ESTADOS_AL_DIA.includes(x.estado)), porHacer: lista.filter((x) => !ESTADOS_AL_DIA.includes(x.estado)) }
}

// «Subido a mano y por correo» etc., para la línea de cada extracto.
export function textoOrigenes(origenes) {
  const t = (origenes || []).map((o) => (o === 'correo' ? 'correo' : 'archivo'))
  return [...new Set(t)].join(' + ')
}

// Leyenda de la cobertura por mes: el color nunca va solo.
export const LEYENDA_COBERTURA = [
  { clave: 'conciliado', texto: 'Revisado' },
  { clave: 'parcial', texto: 'Por revisar' },
  { clave: 'extracto_pendiente', texto: 'Sin procesar' },
  { clave: 'falta_clave', texto: 'Necesita clave' },
  { clave: 'no_se_pudo_leer', texto: 'No se pudo leer' },
  { clave: 'sin_extracto', texto: 'Sin extracto' },
  { clave: 'anterior', texto: 'Anterior a tu fecha de inicio' },
]

// Detalle en palabras de una celda (cuenta + mes) al tocarla.
export function textoDetalleCelda(c) {
  if (!c) return ''
  if (c.estado === 'anterior') return 'Este mes es anterior a tu fecha de inicio: no se espera nada.'
  const partes = []
  if (c.leidas) {
    partes.push(`${c.leidas} ${c.leidas === 1 ? 'movimiento leído' : 'movimientos leídos'} del extracto`)
    partes.push(`${c.ya_estaban} ya estaban`)
    partes.push(`${c.nuevas_agregadas} ${c.nuevas_agregadas === 1 ? 'nuevo' : 'nuevos'}`)
    if (c.por_revisar) partes.push(`${c.por_revisar} por revisar`)
    if (c.por_confirmar) partes.push(`${c.por_confirmar} por confirmar`)
    return partes.join(' · ')
  }
  const mov = `${c.movimientos} ${c.movimientos === 1 ? 'movimiento' : 'movimientos'} este mes`
  return `${mov} · ${c.conciliados ? `${c.conciliados} confirmados con el banco` : 'ninguno confirmado con un extracto todavía'} · ${c.por_confirmar} por confirmar`
}
