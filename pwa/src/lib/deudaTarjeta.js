// La tarjeta de crédito es DEUDA, no saldo: «Debes $X · Cupo $C · Disponible $D», barra de uso del cupo, corte, pago
// hasta y pago mínimo. Los números vienen del servidor en vivo (GET /cuentas/tarjetas/vista, deuda_tarjeta.vista);
// aquí solo se dicen en palabras. Puro y probado en test/deuda_tarjeta.test.jsx.
import { textoFechasTarjeta } from './fechasTarjeta'

/** «Corte 15 oct · Pago hasta 4 nov» a partir de la vista de la tarjeta ('' si no hay corte). */
export const textoCortePago = (v) => textoFechasTarjeta({ corte: v?.corte, limite_pago: v?.limite_pago })

/** Datos listos para mostrar; null si la vista no es de una tarjeta. `fmt(valor, moneda)` da el dinero en texto. */
export function datosDeuda(v, fmt, moneda = 'COP') {
  if (!v || v.tarjeta === false) return null
  const hayCupo = v.cupo != null && v.cupo > 0
  return {
    debes: fmt(v.deuda || 0, moneda),
    alDia: !(v.deuda > 0.5),
    cupo: hayCupo ? fmt(v.cupo, moneda) : null,
    disponible: hayCupo && v.disponible != null ? fmt(v.disponible, moneda) : null,
    usoPct: hayCupo ? Math.max(0, Math.min(100, Number(v.uso_pct) || 0)) : null,
    corte: textoCortePago(v),
    pagoMinimo: v.pago_minimo != null && v.pago_minimo > 0.5 ? fmt(v.pago_minimo, moneda) : null,
    aFavor: !!v.a_favor,
  }
}

/**
 * Cómo se DICE una tarjeta de crédito a partir de su saldo contable (saldo = −deuda). Puro: no cambia la contabilidad,
 * solo la presenta. Nunca devuelve un número con signo: la deuda se dice «Debes $X» y el saldo positivo «Saldo a favor $X».
 * `cupo` y `disponible` solo salen si hay cupo definido (> 0); si no, no se inventan. Cupo excedido: disponible 0 y
 * `excedido` = cuánto te pasaste.
 * @returns {{estado:'deuda'|'a_favor'|'al_dia', etiqueta:string, monto:string, cupo:string|null, disponible:string|null,
 *   usoPct:number|null, excedido:string|null, linea:string}}
 */
export function resumenDeuda(entrada = {}, fmt, moneda = 'COP') {
  const { saldo = 0, disponible = null } = entrada
  let { cupo = null } = entrada
  const s = Number(saldo) || 0
  const estado = s < -0.5 ? 'deuda' : s > 0.5 ? 'a_favor' : 'al_dia'
  const deuda = estado === 'deuda' ? -s : 0
  // El backend siempre entrega el disponible; si no llegó el cupo, se deduce (cupo = deuda + disponible)
  if ((cupo == null || Number(cupo) <= 0) && disponible != null) cupo = deuda + Number(disponible)
  const hayCupo = cupo != null && Number(cupo) > 0
  const libre = hayCupo ? Math.max(0, disponible != null ? Number(disponible) : Number(cupo) - deuda) : null
  const pasado = hayCupo && deuda > Number(cupo) + 0.5 ? deuda - Number(cupo) : 0
  const etiqueta = estado === 'a_favor' ? 'Saldo a favor' : 'Debes'
  const monto = fmt(estado === 'a_favor' ? s : deuda, moneda)
  const cupoTxt = hayCupo ? fmt(Number(cupo), moneda) : null
  const dispTxt = hayCupo ? fmt(libre, moneda) : null
  return {
    estado,
    etiqueta,
    monto,
    cupo: cupoTxt,
    disponible: dispTxt,
    usoPct: hayCupo ? Math.max(0, Math.min(100, (deuda / Number(cupo)) * 100)) : null,
    excedido: pasado > 0 ? fmt(pasado, moneda) : null,
    linea: [`${etiqueta} ${monto}`, dispTxt != null && estado !== 'a_favor' ? `Cupo disponible ${dispTxt}` : null].filter(Boolean).join(' · '),
  }
}
