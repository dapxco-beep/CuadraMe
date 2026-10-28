// Funciones puras del módulo Patrimonio (sin React ni red), para poder probarlas
// con casos numéricos. El cálculo oficial (rentabilidad, XIRR, patrimonio neto)
// lo hace el backend; aquí solo hay lo necesario para dibujar y para la vista
// previa del formulario.

import { aFecha } from './fechaLocal'
import { Car, Package, ChartPie, Coins, Globe, House, Landmark, TrendingUp, Wallet } from 'lucide-react'

export const CLASES = {
  cdt: { label: 'CDT', icono: Landmark },
  fondo: { label: 'Fondo de inversión', icono: ChartPie },
  etf: { label: 'ETF', icono: Globe },
  accion: { label: 'Acción', icono: TrendingUp },
  cripto: { label: 'Cripto', icono: Coins },
  inmueble: { label: 'Inmueble', icono: House },
  vehiculo: { label: 'Vehículo', icono: Car },
  otro: { label: 'Otro bien', icono: Package },
  cuentas: { label: 'Efectivo y cuentas', icono: Wallet },
}

export const CLASES_MERCADO = ['fondo', 'etf', 'accion', 'cripto']
export const CLASES_BIEN = ['inmueble', 'vehiculo', 'otro']

// Colores de la dona: salen de los tokens del tema (claro/oscuro) mezclados con tinta
// para tener ocho tonos distinguibles sin hardcodear hexadecimales.
export const COLORES_DONA = [
  'var(--color-accent)',
  'var(--color-accent-2)',
  'var(--color-ink)',
  'color-mix(in srgb, var(--color-accent) 55%, var(--color-ink))',
  'color-mix(in srgb, var(--color-accent-2) 55%, var(--color-ink))',
  'color-mix(in srgb, var(--color-accent) 45%, var(--color-paper))',
  'color-mix(in srgb, var(--color-accent-2) 45%, var(--color-paper))',
  'color-mix(in srgb, var(--color-ink) 45%, var(--color-paper))',
]

const MESES_CORTOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

// '2026-10' -> 'Oct'
export function etiquetaMes(clave) {
  const [, mes] = String(clave).split('-')
  return MESES_CORTOS[parseInt(mes, 10) - 1] || ''
}

// 12.345 -> '+12,3 %'; null -> '—'
export function formatPct(valor, decimales = 1) {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return '—'
  const signo = valor > 0 ? '+' : ''
  return `${signo}${valor.toFixed(decimales).replace('.', ',')} %`
}

// Valor de un CDT a una fecha: capital * (1 + EA)^(días/365). Misma fórmula que el
// backend (Act/365); sirve para la vista previa mientras se llena el formulario.
export function valorCDT(capital, tasaEA, inicio, fecha, vencimiento = null) {
  if (!(capital > 0) || !(tasaEA >= 0)) return 0
  const fecha_ = (v) => aFecha(v) ?? new Date(NaN)
  let f = fecha_(fecha)
  if (vencimiento && f > fecha_(vencimiento)) f = fecha_(vencimiento)
  const dias = Math.max(0, (f - fecha_(inicio)) / 86400000)
  return capital * Math.pow(1 + tasaEA / 100, dias / 365)
}

// Arcos de la dona. Con radio r, la circunferencia es 2πr; cada porción es un
// trazo (dasharray) con su desplazamiento (dashoffset) acumulado. Se deja un
// pequeño hueco entre porciones solo si hay más de una.
export function arcosDona(distribucion, radio = 40, hueco = 1.2) {
  const circ = 2 * Math.PI * radio
  const total = distribucion.reduce((s, d) => s + d.pct, 0)
  if (!total) return []
  const separar = distribucion.length > 1 ? hueco : 0
  let acumulado = 0
  return distribucion.map((d, i) => {
    const largo = (d.pct / total) * circ
    const arco = {
      clase: d.clase,
      color: COLORES_DONA[i % COLORES_DONA.length],
      largo: Math.max(0, largo - separar),
      resto: circ - Math.max(0, largo - separar),
      desplazamiento: -acumulado,
      pct: d.pct,
    }
    acumulado += largo
    return arco
  })
}

// Puntos (x, y) de la serie dentro de un viewBox ancho x alto con margen. Con un
// solo punto, se centra. El eje Y se escala entre el mínimo y el máximo (con 8 %
// de aire) para que las variaciones pequeñas se noten.
export function puntosSerie(valores, ancho = 100, alto = 60, margen = 4) {
  if (!valores.length) return []
  const min = Math.min(...valores)
  const max = Math.max(...valores)
  const aire = (max - min) * 0.08 || Math.abs(max) * 0.05 || 1
  const lo = min - aire
  const hi = max + aire
  return valores.map((v, i) => ({
    x: valores.length === 1 ? ancho / 2 : margen + (i / (valores.length - 1)) * (ancho - 2 * margen),
    y: margen + (1 - (v - lo) / (hi - lo)) * (alto - 2 * margen),
  }))
}

export function trazoLinea(puntos) {
  return puntos.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ')
}

export function trazoArea(puntos, alto = 60) {
  if (!puntos.length) return ''
  const base = alto
  return `${trazoLinea(puntos)} L${puntos[puntos.length - 1].x.toFixed(2)},${base} L${puntos[0].x.toFixed(2)},${base} Z`
}

// Variación entre el último y el penúltimo valor de la serie.
export function variacion(valores) {
  if (valores.length < 2) return null
  const antes = valores[valores.length - 2]
  const ahora = valores[valores.length - 1]
  return { absoluta: ahora - antes, pct: antes ? ((ahora - antes) / Math.abs(antes)) * 100 : null }
}
