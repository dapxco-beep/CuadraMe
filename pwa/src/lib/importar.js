// Lógica de la pantalla "Importar Excel / CSV" separada de la interfaz para poder probarla.

export const MAX_BYTES = 5 * 1024 * 1024
export const EXTENSIONES = ['csv', 'txt', 'xlsx', 'xls']

export const CAMPOS_MAPEO = [
  { id: 'fecha', etiqueta: 'Fecha', ayuda: 'Día del movimiento' },
  { id: 'descripcion', etiqueta: 'Descripción', ayuda: 'Detalle o concepto' },
  { id: 'monto', etiqueta: 'Monto (con signo)', ayuda: 'Una sola columna: negativo = gasto, positivo = ingreso' },
  { id: 'debito', etiqueta: 'Débito / salidas', ayuda: 'Si el banco separa lo que sale' },
  { id: 'credito', etiqueta: 'Crédito / entradas', ayuda: 'Si el banco separa lo que entra' },
  { id: 'saldo', etiqueta: 'Saldo', ayuda: 'Solo informativo' },
  { id: 'tipo', etiqueta: 'Tipo (D/C)', ayuda: 'Columna con D/C, Débito/Crédito, Cargo/Abono' },
]

export const ETIQUETA_ESTADO = {
  nuevo: 'Nuevo',
  posible_duplicado: 'Posible duplicado',
  duplicado: 'Ya registrado',
}

export function extensionValida(nombre) {
  const ext = (nombre || '').toLowerCase().split('.').pop()
  return EXTENSIONES.includes(ext)
}

// Qué filas llegan marcadas: solo las nuevas. Una posible duplicada la decide el
// usuario; una ya registrada no se puede marcar (importarla duplicaría el movimiento).
export function seleccionInicial(propuesta) {
  return new Set(propuesta.filter((p) => p.estado === 'nuevo').map((p) => p.fila))
}

export function categoriasIniciales(propuesta) {
  return Object.fromEntries(propuesta.map((p) => [p.fila, p.categoria || 'Otros']))
}

export function construirFilas(propuesta, seleccion, categorias) {
  return propuesta
    .filter((p) => seleccion.has(p.fila) && p.estado !== 'duplicado')
    .map((p) => ({
      fecha: p.fecha,
      descripcion: p.descripcion,
      monto: p.monto,
      tipo: p.tipo,
      categoria: categorias[p.fila] || p.categoria || 'Otros',
    }))
}

// Cuánto cambiaría el saldo de la cuenta si se importan estas filas.
export function efectoSaldo(filas) {
  return filas.reduce((s, f) => s + (f.tipo === 'income' ? f.monto : -f.monto), 0)
}

// Opciones de categoría de una fila: las del usuario + "Pago de tarjeta" (no es un gasto).
export function opcionesCategoria(nombres, actual) {
  const base = [...nombres]
  if (!base.includes('Pago de tarjeta')) base.push('Pago de tarjeta')
  if (actual && !base.includes(actual)) base.push(actual)
  return base
}
