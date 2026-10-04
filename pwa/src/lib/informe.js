// Utilidades puras de informes y gráficas (sin React): montos abreviados, escala del
// eje Y, periodos de fecha y selección de meses de la tendencia. Se prueban en
// src/test/informes.test.jsx.

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
export const MESES_CORTOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

// 1234567 -> "$1,2M"; 450000 -> "$450k"; 950 -> "$950"; -2500000 -> "-$2,5M".
export function abreviarCOP(valor) {
  const v = Number(valor) || 0
  const a = Math.abs(v)
  const signo = v < 0 ? '-' : ''
  const dec = (x) => {
    const r = Math.round(x * 10) / 10
    return String(r).replace('.', ',')
  }
  if (a >= 1e9) return `${signo}$${dec(a / 1e9)}MM`
  if (a >= 1e6) return `${signo}$${dec(a / 1e6)}M`
  if (a >= 1e3) return `${signo}$${Math.round(a / 1e3)}k`
  return `${signo}$${Math.round(a)}`
}

// Escala "bonita" para el eje Y: pasos 1, 2, 2.5, 5 x 10^n. Incluye siempre el 0.
export function escala(min, max, n = 4) {
  const lo0 = Math.min(0, min)
  const hi0 = Math.max(0, max)
  const rango = Math.max(hi0 - lo0, 1)
  const bruto = rango / n
  const pot = Math.pow(10, Math.floor(Math.log10(bruto)))
  const f = bruto / pot
  const paso = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * pot
  const lo = Math.floor(lo0 / paso) * paso
  const hi = Math.max(Math.ceil(hi0 / paso) * paso, paso)
  const ticks = []
  for (let t = lo; t <= hi + paso / 1000; t += paso) ticks.push(Math.round(t * 1000) / 1000)
  return { min: lo, max: hi, paso, ticks }
}

export function nombreMesLargo(clave) {
  const [a, m] = clave.split('-').map(Number)
  return `${MESES[m - 1]} de ${a}`
}

export function etiquetaMesCorta(clave) {
  return MESES_CORTOS[parseInt(clave.split('-')[1], 10) - 1]
}

export function tieneDatos(m) {
  return !!(m.ingresos || m.gastos || m.num_movimientos)
}

// Últimos `n` meses de la serie (que viene ordenada de más viejo a más nuevo).
// Con vacios=false se saltan los meses sin movimientos; con true se conservan (atenuados).
export function seleccionarMeses(meses, n, vacios = false) {
  const ventana = meses.slice(-n)
  return vacios ? ventana : ventana.filter(tieneDatos)
}

// ── fechas ─────────────────────────────────────────────────────────

export function aISO(fecha) {
  const f = new Date(fecha)
  return `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}-${String(f.getDate()).padStart(2, '0')}`
}

// { desde, hasta } (AAAA-MM-DD, ambos inclusive) de un periodo con nombre.
export function rangoPeriodo(periodo, hoy = new Date()) {
  const d = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate())
  const dias = (n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() - n)
  switch (periodo) {
    case '7_dias':
      return { desde: aISO(dias(6)), hasta: aISO(d) }
    case '30_dias':
      return { desde: aISO(dias(29)), hasta: aISO(d) }
    case '5_semanas':
      return { desde: aISO(dias(34)), hasta: aISO(d) }
    case 'semana': {
      const lunes = dias((d.getDay() + 6) % 7)
      return { desde: aISO(lunes), hasta: aISO(d) }
    }
    case 'semana_pasada': {
      const lunes = dias(((d.getDay() + 6) % 7) + 7)
      return { desde: aISO(lunes), hasta: aISO(new Date(lunes.getFullYear(), lunes.getMonth(), lunes.getDate() + 6)) }
    }
    case 'este_mes':
      return { desde: aISO(new Date(d.getFullYear(), d.getMonth(), 1)), hasta: aISO(d) }
    case 'mes_pasado':
      return { desde: aISO(new Date(d.getFullYear(), d.getMonth() - 1, 1)), hasta: aISO(new Date(d.getFullYear(), d.getMonth(), 0)) }
    case '3_meses':
      return { desde: aISO(new Date(d.getFullYear(), d.getMonth() - 2, 1)), hasta: aISO(d) }
    case 'anio':
      return { desde: aISO(new Date(d.getFullYear(), 0, 1)), hasta: aISO(d) }
    default:
      return { desde: aISO(d), hasta: aISO(d) }
  }
}

export function diasEntre(desde, hasta) {
  const a = new Date(`${desde}T00:00:00`)
  const b = new Date(`${hasta}T00:00:00`)
  return Math.round((b - a) / 86400000) + 1
}

export function rangoValido(desde, hasta, maxDias = 400) {
  if (!desde || !hasta) return false
  const n = diasEntre(desde, hasta)
  return n >= 1 && n <= maxDias
}

// Arma la cuadrícula del mapa de calor: semanas (lunes a domingo) con celdas
// null para los días fuera del rango. `dias` = [{dia, gasto}].
export function cuadriculaSemanas(dias) {
  if (!dias.length) return []
  const primero = new Date(`${dias[0].dia}T00:00:00`)
  const relleno = (primero.getDay() + 6) % 7
  const celdas = [...Array(relleno).fill(null), ...dias]
  while (celdas.length % 7) celdas.push(null)
  const semanas = []
  for (let i = 0; i < celdas.length; i += 7) semanas.push(celdas.slice(i, i + 7))
  return semanas
}

export function pctTexto(x) {
  if (x === null || x === undefined) return '—'
  const r = Math.round(x * 10) / 10
  return `${r > 0 ? '+' : ''}${String(r).replace('.', ',')} %`
}
