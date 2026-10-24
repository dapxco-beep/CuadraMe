import { tiposEfectivos } from './contabilidad'
// Reglas puras del Inicio simplificado: qué es «el siguiente paso» y cuánto se gastó esta semana.
// Sin React, fáciles de probar.

/**
 * UN solo siguiente paso, según el estado real:
 *   sin cuentas -> crear cuenta · sin movimientos -> traer movimientos ·
 *   movimientos sin tipo -> ponerles tipo · todo al día -> mirar el presupuesto.
 */
export function siguientePasoInicio({ cuentas = 0, movimientos = 0, sinCategorizar = 0 } = {}) {
  if (cuentas < 1) {
    return {
      id: 'cuenta',
      titulo: 'Crea tu primera cuenta',
      apoyo: 'Efectivo, Nequi o tu banco: la que más uses. Toma un minuto.',
      ruta: '/cuentas',
      accion: 'Crear mi cuenta',
    }
  }
  if (movimientos < 1) {
    return {
      id: 'traer',
      titulo: 'Trae tus movimientos',
      apoyo: 'Desde el correo de tu banco, un extracto o un Excel. También puedes anotar uno a mano.',
      ruta: '/sincronizacion',
      accion: 'Traer movimientos',
    }
  }
  if (sinCategorizar > 0) {
    return {
      id: 'categorizar',
      titulo: 'Ordena lo que más pesa (opcional)',
      apoyo: 'No hace falta todo: con los comercios que más pesan o se repiten ya ves en qué se va tu plata.',
      ruta: '/categorizar',
      accion: 'Ver lo que más pesa',
    }
  }
  return {
    id: 'presupuesto',
    titulo: 'Mira tu presupuesto',
    apoyo: 'Todo está al día. Mira cuánto llevas gastado frente a tu límite del mes.',
    ruta: '/presupuesto',
    accion: 'Ver presupuesto',
  }
}

/** Fecha 'YYYY-MM-DD' de hace `dias` días (hora local). */
export function fechaHace(dias, ahora = new Date()) {
  const d = new Date(ahora)
  d.setDate(d.getDate() - dias)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** Suma de los gastos de los últimos 7 días (los traslados entre cuentas propias no cuentan). */
export function gastosDeLaSemana(movimientos, ahora = new Date(), ctx = {}) {
  const desde = fechaHace(6, ahora)
  const lista = movimientos || []
  const te = tiposEfectivos(lista, ctx) // regla única (lib/contabilidad): sin traslados ni pagos de tarjeta
  return lista
    .filter((m) => te[m.id] === 'expense' && String(m.fecha || '').slice(0, 10) >= desde)
    .reduce((s, m) => s + Math.abs(Number(m.monto) || 0), 0)
}

/** Cuentas propias (no tarjetas) en pesos con saldo por debajo de cero: explican un «disponible» negativo. */
export function cuentasEnNegativo(cuentas = []) {
  return (cuentas || [])
    .filter((c) => c.tipo !== 'credito' && (c.moneda || 'COP') === 'COP' && Number(c.saldo) < 0)
    .sort((a, b) => Number(a.saldo) - Number(b.saldo))
}
