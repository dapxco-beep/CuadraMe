// Cómo se agrupan las cuentas en la lista: lo que tienes (cuentas y efectivo), lo que debes (tarjetas) y lo invertido.
export const GRUPOS_DE_CUENTAS = [
  { id: 'cuentas', titulo: 'Cuentas y efectivo', es: (c) => c.tipo !== 'credito' && c.tipo !== 'inversion' },
  { id: 'tarjetas', titulo: 'Tarjetas de crédito', es: (c) => c.tipo === 'credito' },
  { id: 'inversion', titulo: 'Inversiones', es: (c) => c.tipo === 'inversion' },
]

/** [{id, titulo, items}] solo con los grupos que tienen cuentas, conservando el orden de la lista. */
export function agruparCuentas(cuentas) {
  return GRUPOS_DE_CUENTAS
    .map((g) => ({ id: g.id, titulo: g.titulo, items: (cuentas || []).filter(g.es) }))
    .filter((g) => g.items.length > 0)
}

/** Suma de saldos del grupo en pesos (solo cuentas en COP: sumar monedas distintas engañaría). null si no hay nada que sumar. */
export function subtotalGrupo(items) {
  const cop = (items || []).filter((c) => (c.moneda || 'COP') === 'COP')
  if (!cop.length) return null
  return cop.reduce((s, c) => s + (Number(c.saldo) || 0), 0)
}
