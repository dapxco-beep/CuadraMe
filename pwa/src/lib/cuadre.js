// Estado honesto del «cuadre» del Inicio. Antes, con saldo $0 y nada comprometido, la diferencia
// era 0 (>= 0) y la app decía «Tus cuentas cuadran» sin tener datos. Aquí se decide qué decir:
//   sin_datos -> no hay cuentas o todas están en $0 sin compromisos: no se puede afirmar nada
//   parcial   -> hay saldo, pero alguna cuenta está en $0 sin movimientos, o el saldo es $0 y
//                hay compromisos: el resultado es provisional
//   falta     -> con datos reales, lo comprometido supera lo que hay
//   cuadra    -> con datos reales, alcanza
export function estadoCuadre({ cuentas = [], bolsillo = null, movimientos = [], resumen = null } = {}) {
  if (!bolsillo) return { estado: 'cargando', cuadra: null, diferencia: null }
  const diferencia = Number(bolsillo.disponible_real) || 0
  const saldo = Number(bolsillo.saldo_total) || 0
  const comprometido =
    (Number(bolsillo.recurrentes_pendientes_mes) || 0) + (Number(bolsillo.aportes_comprometidos_mes) || 0)
  const sinMovimientos = resumen ? !resumen.hay_movimientos : (movimientos || []).length === 0
  if (!cuentas.length || (saldo <= 0 && comprometido <= 0)) {
    return { estado: 'sin_datos', cuadra: null, diferencia }
  }
  const enCero = cuentas.filter((c) => !Number(c.saldo)).length
  if (saldo <= 0 || (enCero > 0 && sinMovimientos)) {
    return { estado: 'parcial', cuadra: null, diferencia, enCero }
  }
  return { estado: diferencia >= 0 ? 'cuadra' : 'falta', cuadra: diferencia >= 0, diferencia }
}
