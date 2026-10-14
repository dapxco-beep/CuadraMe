// Funciones puras del módulo Inversiones (sin React ni red). Los cálculos oficiales
// (costo promedio, rentabilidad, TIR) los hace el backend; aquí solo textos y formato.

export const AVISO_EDUCATIVO = 'Información educativa, no es asesoría de inversión.'

export const TIPOS_POSICION = [
  { id: 'accion', label: 'Acción', ejemplo: 'Ej. Ecopetrol, Apple' },
  { id: 'etf', label: 'ETF', ejemplo: 'Ej. VOO, SPY' },
  { id: 'fondo', label: 'Fondo / FIC', ejemplo: 'Ej. fondo de Skandia o una fiduciaria' },
  { id: 'cripto', label: 'Cripto', ejemplo: 'Ej. BTC, ETH' },
  { id: 'cdt', label: 'CDT / depósito', ejemplo: 'Ej. CDT a 360 días' },
  { id: 'fiducia', label: 'Fiducia', ejemplo: 'Ej. fiducia de inversión' },
]

export const ETIQUETA_TIPO = {
  ...Object.fromEntries(TIPOS_POSICION.map((t) => [t.id, t.label])),
  accion: 'Acciones',
  etf: 'ETF',
}

export const TIPOS_BROKER = ['acciones', 'etf', 'fondos', 'cripto', 'cdt', 'fiducia']

// Plataformas frecuentes en Colombia/LATAM: solo sugerencias para no escribir (no es una recomendación).
export const BROKERS_SUGERIDOS = [
  'Trii', 'Tyba', 'Valores Bancolombia', 'Davivienda Corredores', 'Interactive Brokers', 'Hapi', 'XTB', 'eToro',
  'Binance', 'Skandia', 'Fiduciaria',
]

export const GLOSARIO = [
  ['Ticker', 'El código corto con el que se identifica una acción o un fondo en la bolsa. Ej. ECOPETROL o VOO.'],
  ['Costo promedio', 'Lo que en promedio pagaste por cada unidad, contando todas tus compras y comisiones.'],
  ['Ganancia no realizada', 'Lo que ganarías o perderías si vendieras hoy. Mientras no vendas, puede cambiar.'],
  ['Ganancia realizada', 'La que ya quedó en tu bolsillo porque vendiste.'],
  ['TIR (rentabilidad anual)', 'Cuánto rindió tu plata por año, teniendo en cuenta cuándo pusiste o sacaste cada aporte.'],
]

export function colorSigno(v) {
  if (v === null || v === undefined || v === 0) return 'text-ink-soft'
  return v > 0 ? 'text-accent' : 'text-danger'
}

export function pctTexto(v, dec = 1) {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return `${v > 0 ? '+' : ''}${v.toFixed(dec).replace('.', ',')} %`
}

// Texto del estado del precio: honesto y corto.
export function textoEstadoPrecio(p) {
  if (p.precio === null || p.precio === undefined) return p.precio_mensaje || 'Sin precio: agrégalo a mano'
  if (p.precio_estado === 'en_vivo') return 'En vivo'
  if (p.precio_estado === 'manual') return p.precio_mensaje ? `Manual · ${p.precio_mensaje}` : 'Manual'
  return p.precio_mensaje || 'Retrasado'
}

// Texto de «actualizado hace X» a partir de una fecha ISO.
export function haceCuanto(iso, ahora = new Date()) {
  if (!iso) return ''
  const d = Math.floor((ahora - new Date(iso)) / 86400000)
  if (d <= 0) return 'hoy'
  if (d === 1) return 'hace 1 día'
  if (d < 30) return `hace ${d} días`
  const m = Math.floor(d / 30)
  return m < 12 ? `hace ${m} ${m === 1 ? 'mes' : 'meses'}` : 'hace más de un año'
}

// Convierte la serie de evolución al formato que ya dibuja GraficoPatrimonio.
export function serieEvolucion(evolucion = []) {
  return evolucion.map((e) => ({ mes: e.mes, patrimonio_neto: e.valor }))
}

// Aviso de concentración (mismo umbral que el consejo del backend).
export const CONCENTRACION_MAX = 40
export function hayConcentracion(c, nPosiciones) {
  return Boolean(c && nPosiciones > 1 && c.pct > CONCENTRACION_MAX)
}

// Primera vista previa del CSV de importación en el navegador no hace falta: la hace el servidor.
export const EJEMPLO_CSV = 'ticker,cantidad,costo\nECOPETROL,100,2300\nVOO,2,420'
