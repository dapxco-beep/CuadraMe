// Cierre de mes contra el extracto: textos y reglas puras (sin React) para probarlas fácil.
// Los números ya vienen calculados del servidor (GET /cierre-mes/extractos): aquí solo se dicen en palabras.

/** Frase corta de un banco para la fila de arriba: «Nu: ✓», «Nequi: ✕ $39.496», «Beta: sin extracto». */
export function textoBanco(b, fmt) {
  if (!b) return ''
  if (b.estado === 'cuadra') return `${b.banco}: ✓`
  if (b.estado === 'no_cuadra') return `${b.banco}: ✕ ${fmt(Math.abs(b.diferencia || 0))}`
  return `${b.banco}: sin extracto`
}

/** «No cuadra por $40.000» / «Cuadra» / «Sin extracto» de una cuenta. */
export function estadoCuenta(c, fmt) {
  if (!c) return ''
  if (c.estado === 'cuadra') return 'Cuadra'
  if (c.estado === 'no_cuadra') return `No cuadra por ${fmt(Math.abs(c.diferencia || 0), c.moneda)}`
  return 'Sin extracto'
}

/** Con dinero que entra se muestra «+», con el que sale «−»; el cero va sin signo. */
export function conSigno(valor, fmt, moneda, { invertir = false } = {}) {
  const v = Number(valor) || 0
  if (Math.abs(v) < 0.5) return fmt(0, moneda)
  const positivo = invertir ? v < 0 : v > 0
  return `${positivo ? '+' : '−'}${fmt(Math.abs(v), moneda)}`
}

/** Etiqueta de cada tipo de «otro movimiento». */
export const CLASE_OTRO = {
  traslado: 'Pasaste plata entre tus cuentas',
  pago_tarjeta: 'Pago de tarjeta',
  ajuste: 'Ajuste de saldo',
  otro: 'Otro movimiento',
}

/** «Del 5 may al 4 jun» cuando el periodo del banco no es el mes calendario; si lo es, nada. */
export function textoPeriodo(p) {
  if (!p || p.mes_completo) return ''
  const corta = (iso) => {
    const [a, m, d] = String(iso).slice(0, 10).split('-').map(Number)
    const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
    return a ? `${d} ${meses[m - 1]}` : ''
  }
  return `Del ${corta(p.desde)} al ${corta(p.hasta)}`
}

/** De dónde sale el «Empecé con». */
export function origenEmpece(c) {
  return c?.empece_origen === 'extracto' ? 'según tu extracto' : 'lo que calculó la app'
}
