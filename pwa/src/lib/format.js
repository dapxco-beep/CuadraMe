const COP = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

export function formatCOP(value) {
  return COP.format(value)
}

const formateadores = new Map()

// Formatea según la moneda de la cuenta (COP, USD, EUR...). Las cuentas en
// dólares mostraban el saldo con formato de pesos; esto respeta la moneda real.
export function formatMoneda(value, moneda = 'COP') {
  if (!moneda || moneda === 'COP') return COP.format(value)
  if (!formateadores.has(moneda)) {
    try {
      formateadores.set(
        moneda,
        new Intl.NumberFormat('es-CO', { style: 'currency', currency: moneda, maximumFractionDigits: 2 })
      )
    } catch {
      // código de moneda inválido: se cae a pesos en vez de romper la pantalla
      formateadores.set(moneda, COP)
    }
  }
  return formateadores.get(moneda).format(value)
}
