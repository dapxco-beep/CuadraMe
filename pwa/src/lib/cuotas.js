// Compras a cuotas con tarjeta. La cuota se calcula igual que en el backend
// (app/cuotas.py): sin interés es total / n; con interés, fórmula francesa
//   cuota = total * i / (1 - (1 + i)^-n)   con i = tasa mensual en decimal.

export function calcularCuota(total, n, tasaMensualPct = 0) {
  const t = Number(total)
  const meses = Math.floor(Number(n))
  if (!(t > 0) || !(meses >= 1)) return 0
  const i = (Number(tasaMensualPct) || 0) / 100
  const cuota = i > 0 ? (t * i) / (1 - (1 + i) ** -meses) : t / meses
  return Math.round(cuota)
}

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

// "2027-09" -> "sep 2027"
export function mesAnio(aaaamm) {
  if (!aaaamm) return ''
  const [a, m] = aaaamm.split('-')
  return `${MESES[parseInt(m, 10) - 1]} ${a}`
}

// Lo que vence este mes en cuotas (suma de lo que traen los planes que no han terminado).
export function comprometidoEsteMes(planes) {
  return (planes || []).filter((p) => p.vence_este_mes && !p.terminado).reduce((s, p) => s + p.cuota_mensual, 0)
}
