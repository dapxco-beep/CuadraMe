// Regla contable en el cliente (espejo de backend/app/contabilidad.py): el pago de una
// tarjeta de crédito y los traslados entre cuentas propias NO son gasto ni ingreso.
// El servidor es la fuente de verdad de los reportes; esto solo evita que los totales
// que se calculan en pantalla (Movimientos, mapa de calor) cuenten dos veces.

const PAGO_TARJETA =
  /\b(?:pagos?|abonos?)\s+(?:(?:de|a|la|mi|total|minimo|del)\s+)*(?:tarjeta|tarj\.?|tc|tdc|t\.c\.?|visa|master\s?card|amex|american\s+express|diners)\b/i

const CATEGORIAS_NEUTRAS = ['transferencia', 'pago de tarjeta']

function sinAcentos(t) {
  return (t || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
}

export function esPagoTarjeta(descripcion) {
  return PAGO_TARJETA.test(sinAcentos(descripcion))
}

// 'income' | 'expense' | 'transfer'. tiposCuenta: { [cuentaId]: 'ahorro'|'credito'|... } (opcional).
export function tipoEfectivo(m, tiposCuenta = {}) {
  if (m.tipo !== 'income' && m.tipo !== 'expense') return 'transfer'
  if (m.fuente === 'transferencia_interna') return 'transfer'
  if (CATEGORIAS_NEUTRAS.includes(sinAcentos(m.categoria).trim().toLowerCase())) return 'transfer'
  if (m.tipo === 'expense' && esPagoTarjeta(m.descripcion)) return 'transfer'
  if (m.tipo === 'income' && tiposCuenta[m.cuenta_id] === 'credito') return 'transfer'
  return m.tipo
}

export const CATEGORIA_PAGO_TARJETA = 'Pago de tarjeta'
