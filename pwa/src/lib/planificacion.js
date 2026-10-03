// Ayudas PURAS de presentación para planificación (el cálculo de fondo vive en
// el backend: backend/app/planificacion.py). Aquí solo se traduce a pantalla.

export const PERIODOS = [
  { valor: 'monthly', etiqueta: 'Mensual' },
  { valor: 'biweekly', etiqueta: 'Quincenal' },
  { valor: 'weekly', etiqueta: 'Semanal' },
]

export function etiquetaPeriodo(periodo) {
  return PERIODOS.find((p) => p.valor === periodo)?.etiqueta || 'Mensual'
}

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

function partes(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number)
  return { y, m, d }
}

// 'YYYY-MM-DD' (fin EXCLUSIVO) -> 'YYYY-MM-DD' del último día incluido
export function diaAnterior(iso) {
  const { y, m, d } = partes(iso)
  const f = new Date(Date.UTC(y, m - 1, d - 1))
  return f.toISOString().slice(0, 10)
}

// ('2026-10-16', '2026-11-01') -> '16 oct – 31 oct'
export function textoRango(inicio, fin) {
  if (!inicio || !fin) return ''
  const a = partes(inicio)
  const b = partes(diaAnterior(fin))
  return `${a.d} ${MESES[a.m - 1]} – ${b.d} ${MESES[b.m - 1]}`
}

// Posiciones (0-100) de la barra de gasto y del marcador de proyección.
// Si la proyección pasa del límite, el marcador queda pegado al borde y `desborda`
// avisa para pintarlo en alerta.
export function posicionesBarra(item) {
  const limite = item?.limite || 0
  if (limite <= 0) return { usado: 0, marcador: null, desborda: false }
  const usado = Math.min(100, Math.max(0, (item.gastado / limite) * 100))
  const proy = item.proyectado ?? item.gastado
  const rawMarcador = (proy / limite) * 100
  return {
    usado,
    marcador: Math.min(100, Math.max(0, rawMarcador)),
    desborda: rawMarcador > 100,
  }
}

export function colorEstado(estado) {
  if (estado === 'excedido' || estado === 'en_riesgo') return 'var(--color-danger)'
  if (estado === 'atencion') return 'var(--color-accent-2)'
  return 'var(--color-accent)'
}

// Barras apiladas de la descomposición. Cada mes tiene tres aportes que pueden
// ser negativos: se dibujan hacia arriba (positivos) y hacia abajo (negativos)
// sobre una escala común. `meses` = [{mes, ahorro, valorizacion, reduccion_deuda}].
export function escalaDescomposicion(meses) {
  const claves = ['ahorro', 'valorizacion', 'reduccion_deuda']
  let maxArriba = 0
  let maxAbajo = 0
  for (const m of meses) {
    const pos = claves.reduce((s, k) => s + Math.max(0, m[k] || 0), 0)
    const neg = claves.reduce((s, k) => s + Math.min(0, m[k] || 0), 0)
    maxArriba = Math.max(maxArriba, pos)
    maxAbajo = Math.max(maxAbajo, -neg)
  }
  const total = maxArriba + maxAbajo
  return { maxArriba, maxAbajo, total, pctArriba: total ? (maxArriba / total) * 100 : 100 }
}

// Alto (en % de la mitad correspondiente) de un valor dentro de la escala.
export function altoSegmento(valor, escala) {
  const ref = valor >= 0 ? escala.maxArriba : escala.maxAbajo
  return ref ? (Math.abs(valor) / ref) * 100 : 0
}

export const COMPONENTES_CRECIMIENTO = [
  { clave: 'ahorro', etiqueta: 'Ahorro', color: 'var(--color-accent)' },
  { clave: 'valorizacion', etiqueta: 'Valorización', color: 'var(--color-accent-2)' },
  { clave: 'reduccion_deuda', etiqueta: 'Menos deuda', color: 'var(--color-ink-soft)' },
]
