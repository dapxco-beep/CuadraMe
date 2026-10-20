// Fechas de un extracto de TARJETA para mostrar bajo su mes: «Corte 15 oct · Pago hasta 4 nov».
// Vienen del resumen que se leyó del PDF (`tarjeta_fechas`: { corte, limite_pago, estimado }, fechas ISO).
// Si el corte es un cálculo (no se pudo leer el PDF) se dice con «aprox.» para no afirmar de más. Puro y probado.

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

/** '2026-10-15' -> '15 oct'; '' si no es una fecha. */
export function diaCorto(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''))
  if (!m) return ''
  return `${Number(m[3])} ${MESES[Number(m[2]) - 1] || ''}`.trim()
}

/** «Corte 15 oct · Pago hasta 4 nov», «Corte aprox. 15 oct» o '' si no hay corte. */
export function textoFechasTarjeta(f) {
  const corte = diaCorto(f?.corte)
  if (!corte) return ''
  const pago = diaCorto(f?.limite_pago)
  return `Corte ${f?.estimado ? 'aprox. ' : ''}${corte}${pago ? ` · Pago hasta ${pago}` : ''}`
}

/** Solo el corte, para el espacio chico de un mes: «Corte 15 oct». */
export function textoCorte(f) {
  const corte = diaCorto(f?.corte)
  return corte ? `Corte ${f?.estimado ? 'aprox. ' : ''}${corte}` : ''
}
