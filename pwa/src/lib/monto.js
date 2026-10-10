// Montos escritos «a la colombiana» en los formularios: 1250000 -> 1.250.000 y la coma es el decimal.
// El valor CANÓNICO (el que guarda el estado y se envía) es un texto con punto decimal y a lo sumo
// 2 decimales: "1250000" o "1250000.5". Número(canónico) siempre da el valor correcto.
// Dos decimales como máximo evitan que "1.200" canónico se confunda con mil doscientos (miles).

/** Texto que la persona ve en el campo -> valor canónico. Solo cuenta la coma como decimal. */
export function canonicoDesdeEscrito(texto, { decimales = true, negativo = false } = {}) {
  const t = String(texto ?? '')
  const neg = negativo && t.trim().startsWith('-')
  const coma = decimales ? t.indexOf(',') : -1
  const entera = (coma > -1 ? t.slice(0, coma) : t).replace(/\D/g, '').replace(/^0+(?=\d)/, '')
  let salida = entera
  if (coma > -1) {
    const dec = t.slice(coma + 1).replace(/\D/g, '').slice(0, 2)
    salida = `${entera || '0'}.${dec}`
  }
  if (neg && (salida || t.trim() === '-')) salida = `-${salida}`
  return salida
}

/** Valor canónico -> lo que se muestra: "1250000.5" -> "1.250.000,5". Vacío se queda vacío. */
export function mostrarMonto(canonico) {
  let c = String(canonico ?? '')
  if (c === '' || c === '-') return c
  // Valores que no son canónicos (viejos o precargados con separadores) se normalizan primero.
  if (!/^-?\d*\.?\d*$/.test(c)) c = String(leerNumero(c))
  const neg = c.startsWith('-')
  const [ent = '', dec] = c.replace('-', '').split('.')
  const miles = ent.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return `${neg ? '-' : ''}${miles}${dec !== undefined ? `,${dec}` : ''}`
}

/** Texto pegado ("1.250.000", "1,250,000.50", "$ 1250000") -> canónico. */
export function canonicoDesdePegado(texto) {
  const n = leerNumero(texto)
  if (!Number.isFinite(n)) return ''
  return String(Math.round(n * 100) / 100)
}

function leerNumero(texto) {
  let t = String(texto ?? '').replace(/[^\d.,-]/g, '')
  const neg = t.startsWith('-')
  t = t.replace(/-/g, '')
  const coma = t.lastIndexOf(',')
  const punto = t.lastIndexOf('.')
  if (coma > -1 && punto > -1) t = coma > punto ? t.replace(/\./g, '').replace(',', '.') : t.replace(/,/g, '')
  else if (coma > -1) t = t.split(',').length > 2 || t.length - coma - 1 === 3 ? t.replace(/,/g, '') : t.replace(',', '.')
  else if (punto > -1) t = t.split('.').length > 2 || t.length - punto - 1 === 3 ? t.replace(/\./g, '') : t
  const n = Number(t)
  return Number.isFinite(n) ? (neg ? -n : n) : NaN
}

/** Cuántos caracteres «que cuentan» (dígitos, coma, signo) hay antes de la posición `pos`. */
export function significativosAntes(texto, pos) {
  return (String(texto).slice(0, pos).match(/[\d,-]/g) || []).length
}

/** Posición en `texto` justo después del n-ésimo carácter que cuenta. */
export function posicionTrasSignificativos(texto, n) {
  if (n <= 0) return 0
  let visto = 0
  for (let i = 0; i < texto.length; i += 1) {
    if (/[\d,-]/.test(texto[i])) {
      visto += 1
      if (visto === n) return i + 1
    }
  }
  return texto.length
}
