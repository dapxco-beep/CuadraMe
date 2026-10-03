// score 0 → solo tierra (etapa 0). score 100 → árbol florecido (etapa 6).
export function etapaPorScore(score) {
  if (score >= 90) return 6
  if (score >= 75) return 5
  if (score >= 60) return 4
  if (score >= 45) return 3
  if (score >= 30) return 2
  if (score >= 15) return 1
  return 0
}

export const MENSAJE_POR_ETAPA = [
  'Aún no hay nada plantado — registra movimientos para empezar',
  'Apenas germinando, cuidado con los gastos',
  'Creciendo, pero le falta cuidado',
  'Va tomando forma, sigue así',
  'Un árbol saludable',
  'Casi florecido — vas muy bien',
  'Floreciendo — tus finanzas van excelente',
]
