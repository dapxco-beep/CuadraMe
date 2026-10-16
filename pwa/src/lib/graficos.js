// Utilidades PURAS de los gráficos del informe (solo pintan: las cifras vienen del servidor).

/** Etiqueta corta de eje: 1200000 -> «$1,2 M», 85000 -> «$85 k», 0 -> «$0». */
export function abreviarEje(valor) {
  const v = Number(valor) || 0
  const a = Math.abs(v)
  const signo = v < 0 ? '-' : ''
  const dec = (x) => String(Math.round(x * 10) / 10).replace('.', ',')
  if (a >= 1e9) return `${signo}$${dec(a / 1e9)} MM`
  if (a >= 1e6) return `${signo}$${dec(a / 1e6)} M`
  if (a >= 1e3) return `${signo}$${dec(a / 1e3)} k`
  return `${signo}$${Math.round(a)}`
}

/** Escala «bonita»: límites y marcas en pasos 1/2/5 × 10^n que cubren [min, max] (siempre incluye el 0). */
export function escalaBonita(min, max, marcas = 4) {
  const lo = Math.min(0, min)
  const hi = Math.max(0, max)
  if (lo === 0 && hi === 0) return { min: 0, max: 1, ticks: [0, 1] }
  const bruto = (hi - lo) / marcas
  const pot = 10 ** Math.floor(Math.log10(bruto))
  const f = bruto / pot
  const paso = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pot
  const a = Math.floor(lo / paso) * paso
  const b = Math.ceil(hi / paso) * paso
  const ticks = []
  for (let t = a; t <= b + paso / 2; t += paso) ticks.push(Math.round(t / paso) * paso)
  return { min: a, max: b, ticks }
}

/** Trazo suave (spline cúbico monótono: no se «pasa» de los datos) por los puntos [[x, y], ...]. */
export function curvaSuave(pts) {
  const n = pts.length
  if (n === 0) return ''
  if (n === 1) return `M${pts[0][0]},${pts[0][1]}`
  const f = (v) => Math.round(v * 100) / 100
  const dx = []
  const m = []
  const t = []
  for (let i = 0; i < n - 1; i++) {
    dx[i] = pts[i + 1][0] - pts[i][0]
    m[i] = (pts[i + 1][1] - pts[i][1]) / (dx[i] || 1)
  }
  t[0] = m[0]
  t[n - 1] = m[n - 2]
  for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2
  for (let i = 0; i < n - 1; i++) {
    if (m[i] === 0) { t[i] = 0; t[i + 1] = 0; continue }
    const a = t[i] / m[i]
    const b = t[i + 1] / m[i]
    const s = a * a + b * b
    if (s > 9) { const k = 3 / Math.sqrt(s); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i] }
  }
  let d = `M${f(pts[0][0])},${f(pts[0][1])}`
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3
    d += `C${f(pts[i][0] + h)},${f(pts[i][1] + t[i] * h)} ${f(pts[i + 1][0] - h)},${f(pts[i + 1][1] - t[i + 1] * h)} ${f(pts[i + 1][0])},${f(pts[i + 1][1])}`
  }
  return d
}

/** Barra con las esquinas de ARRIBA redondeadas (crece desde `base` hacia arriba). */
export function rutaBarra(x, y, ancho, base, radio = 4) {
  const alto = base - y
  if (alto <= 0) return ''
  const r = Math.min(radio, ancho / 2, alto)
  return `M${x},${base}V${y + r}Q${x},${y} ${x + r},${y}H${x + ancho - r}Q${x + ancho},${y} ${x + ancho},${y + r}V${base}Z`
}

export function pctCorto(pct) {
  if (pct === null || pct === undefined) return null
  return `${Math.abs(Math.round(pct))} %`
}

/** Frase de la evolución de una serie: «En septiembre, Transporte subió 18 % frente a su promedio.» */
function fraseEvolucionBase(nombre, resumen, etiquetaMes = '') {
  if (!resumen) return 'Todavía no hay un mes completo para comparar.'
  const pct = resumen.vs_promedio_pct
  const mes = etiquetaMes ? `En ${etiquetaMes}, ` : ''
  if (pct === null || pct === undefined) return `${mes}${nombre} aún no tiene un promedio para comparar.`
  if (Math.abs(pct) < 3) return `${mes}${nombre} se mantuvo en su promedio.`
  const verbo = pct > 0 ? 'subió' : 'bajó'
  return `${mes}${nombre} ${verbo} ${pctCorto(pct)} frente a su promedio.`
}

export function fraseEvolucion(nombre, resumen, etiquetaMes = '') {
  const f = fraseEvolucionBase(nombre, resumen, etiquetaMes)
  return f.charAt(0).toUpperCase() + f.slice(1)
}
