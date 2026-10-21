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
