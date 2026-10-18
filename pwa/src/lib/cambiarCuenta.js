// «Cambiar la cuenta de este extracto»: textos y reglas puras (sin React) para probarlas fácil.

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`

/** La sugerencia que manda el servidor en cada fila: «Parece de tu tarjeta de crédito. ¿Pasarlo a X?». */
export function textoSugerencia(it) {
  const s = it?.sugerencia_cuenta
  if (!s?.cuenta_id || !it?.puede_cambiar_cuenta) return ''
  return `Parece de tu tarjeta de crédito. ¿Pasarlo a ${s.nombre}?`
}

/** Cuentas a las que se puede pasar: todas menos la actual. */
export function cuentasDestino(cuentas = [], actualId = '') {
  return cuentas.filter((c) => c.id !== actualId)
}

/** Frase de la vista previa: «Moverá 3 movimientos de A a B. El saldo de A pasará de X a Y y el de B de Z a W.» */
export function textoPrevia(p, fmt) {
  if (!p) return ''
  const { origen, destino } = p
  if (p.ya_en_esa_cuenta) return 'Este extracto ya está en esa cuenta.'
  const que = p.movera
    ? `Moverá ${plural(p.movera, 'movimiento', 'movimientos')} de ${origen.nombre} a ${destino.nombre}.`
    : `Pasará el extracto de ${origen.nombre} a ${destino.nombre}. No hay movimientos importados que mover.`
  const saldos = ` El saldo de ${origen.nombre} pasará de ${fmt(origen.saldo_antes)} a ${fmt(origen.saldo_despues)} y el de ${destino.nombre} de ${fmt(destino.saldo_antes)} a ${fmt(destino.saldo_despues)}.`
  const dups = p.duplicados
    ? ` ${plural(p.duplicados, 'movimiento ya estaba', 'movimientos ya estaban')} en ${destino.nombre}: no se repite${p.duplicados === 1 ? '' : 'n'}.`
    : ''
  return que + (p.movera || p.duplicados ? saldos : '') + dups
}

/** Lo que se le dice a la persona al terminar. */
export function textoListo(r) {
  if (!r || r.sin_cambios) return 'Ese extracto ya estaba en esa cuenta.'
  return r.movidos
    ? `Listo: pasamos ${plural(r.movidos, 'movimiento', 'movimientos')} a ${r.destino.nombre}.`
    : `Listo: el extracto ahora es de ${r.destino.nombre}.`
}
