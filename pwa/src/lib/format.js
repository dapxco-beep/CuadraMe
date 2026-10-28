import { formatoActual } from './pais'

const COP = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

// Nombre histórico: formatea en la MONEDA BASE del perfil (moneda base fase 2). Para quien tiene base COP
// (todos hoy) es idéntico a siempre; con otra base (MXN, CLP, PEN...) usa esa moneda y el formato de su país.
// Lo que de verdad es COP (impuestos DIAN) usa `formatCOPFijo`.
const SIN_DATO = '—'

export function formatCOP(value) {
  if (!Number.isFinite(Number(value))) return SIN_DATO
  const { moneda } = formatoActual()
  if (moneda && moneda !== 'COP') return formatMoneda(value, moneda)
  return formatCOPFijo(value)
}

// Siempre pesos colombianos (DIAN/renta: se declara en COP sin importar la moneda base). Fuera de Colombia se
// muestra con el código («COP 1.234») para no hacerlos pasar por pesos locales.
const COP_CODIGO = new Map()
export function formatCOPFijo(value) {
  if (!Number.isFinite(Number(value))) return SIN_DATO
  const { locale } = formatoActual()
  if (locale === 'es-CO') return COP.format(value)
  if (!COP_CODIGO.has(locale)) {
    COP_CODIGO.set(locale, new Intl.NumberFormat(locale, { style: 'currency', currency: 'COP', currencyDisplay: 'code', maximumFractionDigits: 0 }))
  }
  return COP_CODIGO.get(locale).format(value)
}

const formateadores = new Map()

// Formatea según la moneda de la cuenta (COP, USD, EUR...). Las cuentas en
// dólares mostraban el saldo con formato de pesos; esto respeta la moneda real.
// Los separadores y el símbolo siguen al país de la persona (es-MX, es-CL...) sin cambiar
// los montos de quien está en Colombia. Decimales: los de la moneda (COP/CLP sin, el resto 2).
const SIN_DECIMALES = new Set(['COP', 'CLP', 'CRC', 'PYG', 'JPY'])

export function formatMoneda(value, moneda = 'COP') {
  if (!Number.isFinite(Number(value))) return SIN_DATO
  const { locale } = formatoActual()
  if ((!moneda || moneda === 'COP') && locale === 'es-CO') return COP.format(value)
  const mon = moneda || 'COP'
  const clave = `${locale}|${mon}`
  if (!formateadores.has(clave)) {
    try {
      formateadores.set(
        clave,
        new Intl.NumberFormat(locale, {
          style: 'currency',
          currency: mon,
          maximumFractionDigits: SIN_DECIMALES.has(mon) ? 0 : 2,
        })
      )
    } catch {
      // código de moneda inválido: se cae a pesos en vez de romper la pantalla
      formateadores.set(clave, COP)
    }
  }
  return formateadores.get(clave).format(value)
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
  transferencia_interna: 'Plata entre tus cuentas',
  ajuste_saldo: 'Ajuste de saldo',
  cierre_app: 'Cierre de mes',
  aporte_meta: 'Aporte a una meta',
}
export function nombreOrigen(fuente) {
  return ORIGENES[fuente] || 'Otro'
}
