// Presentación de «¿Tengo que declarar renta?»: textos y colores por estado. Las cuentas las hace el servidor
// (backend/app/renta_alerta.py); aquí solo se decide cómo se ve. El color nunca va solo: siempre hay palabra.
export const ESTADO_RENTA = {
  lejos: { etiqueta: 'Lejos del tope', color: 'var(--color-accent-2)' },
  cerca: { etiqueta: 'Cerca del tope', color: 'var(--color-gold)' },
  superado: { etiqueta: 'Superaste el tope', color: 'var(--color-danger)' },
  sin_datos: { etiqueta: 'Faltan datos', color: 'var(--color-line)' },
}

export const ENLACE_DIAN = 'https://www.dian.gov.co'

export function cuentaAtras(plazo) {
  if (!plazo) return ''
  const n = plazo.dias_restantes
  if (n < 0) return plazo.texto
  if (n === 0) return `${plazo.texto}: es hoy`
  return `${plazo.texto} · ${n === 1 ? 'falta 1 día' : `faltan ${n} días`}`
}

// Barra llena hasta el 100 %: pasarse del tope no hace la barra más larga, lo dice el texto.
export const pctBarra = (c) => Math.max(0, Math.min(100, c.pct || 0))
