const COP = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

export function formatCOP(value) {
  return COP.format(value)
}

const formateadores = new Map()

// Formatea según la moneda de la cuenta (COP, USD, EUR...). Las cuentas en
// dólares mostraban el saldo con formato de pesos; esto respeta la moneda real.
export function formatMoneda(value, moneda = 'COP') {
  if (!moneda || moneda === 'COP') return COP.format(value)
  if (!formateadores.has(moneda)) {
    try {
      formateadores.set(
        moneda,
        new Intl.NumberFormat('es-CO', { style: 'currency', currency: moneda, maximumFractionDigits: 2 })
      )
    } catch {
      // código de moneda inválido: se cae a pesos en vez de romper la pantalla
      formateadores.set(moneda, COP)
    }
  }
  return formateadores.get(moneda).format(value)
}

// Un solo formato para porcentajes en toda la app: coma decimal y espacio antes del %.
// 51.1 -> '51,1 %'; 12 -> '12 %'; 51.04 -> '51 %'. `signo: true` agrega '+' a los positivos.
export function formatPorcentaje(valor, { decimales = 1, signo = false } = {}) {
  const n = Number(valor)
  if (valor === null || valor === undefined || !Number.isFinite(n)) return '—'
  const f = 10 ** decimales
  const r = Math.round(n * f) / f
  return `${signo && r > 0 ? '+' : ''}${String(r).replace('.', ',')} %`
}

// '1 vez' / '9 veces' / '9,5 veces'
export function formatVeces(n) {
  const r = Math.round(Number(n) * 10) / 10
  return `${String(r).replace('.', ',')} ${r === 1 ? 'vez' : 'veces'}`
}

// Fecha legible para personas: '1 de agosto de 2026'. Si trae hora real (no medianoche ni
// mediodía de relleno de un archivo) la agrega: '1 de agosto de 2026, 3:45 p. m.'
export function formatFechaLarga(valor) {
  const d = new Date(valor)
  if (Number.isNaN(d.getTime())) return '—'
  const dia = d.toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' })
  const h = d.getHours()
  if (d.getMinutes() === 0 && d.getSeconds() === 0 && (h === 0 || h === 12)) return dia
  return `${dia}, ${d.toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' })}`
}

// El campo `fuente` del backend es un código interno; esto lo traduce a algo que entienda cualquiera.
const ORIGENES = {
  manual: 'Lo anotaste tú',
  email: 'Correo del banco',
  ai: 'Asistente',
  wallet: 'Pago con el celular',
  recurrente: 'Pago recurrente',
  importacion_archivo: 'Archivo importado',
  conciliacion_extracto: 'Extracto del banco',
  conciliacion_auto: 'Extracto del banco',
  transferencia_interna: 'Traslado entre tus cuentas',
  ajuste_saldo: 'Ajuste de saldo',
  cierre_app: 'Cierre de mes',
  aporte_meta: 'Aporte a una meta',
}
export function nombreOrigen(fuente) {
  return ORIGENES[fuente] || 'Otro'
}
