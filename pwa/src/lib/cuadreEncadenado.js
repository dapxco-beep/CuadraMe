import { formatCOP } from './format'

// Cómo se ve cada estado de un mes en la tabla «Cuadre mes a mes» (siempre ícono + texto, nunca solo color).
export const ESTADO_MES = {
  cuadra: { texto: 'Cuadra', clase: 'text-cuadra' },
  diferencia: { texto: 'No cuadra', clase: 'text-accent' },
  solo_saldo_inicial: { texto: 'Falta saldo inicial', clase: 'text-accent' },
  arrastra: { texto: 'Arrastra', clase: 'text-ink-soft' },
  cadena_rota: { texto: 'Hueco', clase: 'text-accent' },
  falta_extracto: { texto: 'Falta extracto', clase: 'text-ink-soft' },
}

// Un monto con signo (+ entra, − sale) para «el banco dice / tu app dice» (cambio del mes).
export function firmado(valor, moneda = 'COP') {
  const v = Number(valor) || 0
  if (Math.abs(v) < 1) return '$0'
  return `${v > 0 ? '+' : '−'}${formatCOP(Math.abs(v), moneda)}`
}

// Filas de la tabla: marca el mes culpable (el primero con diferencia propia, o un saldo inicial que falta).
export function aFilas(meses = []) {
  return meses.map((m) => ({
    ...m,
    culpable: ['diferencia', 'solo_saldo_inicial', 'cadena_rota'].includes(m.estado),
  }))
}
