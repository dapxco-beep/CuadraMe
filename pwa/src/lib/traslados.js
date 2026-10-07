// Traslados entre cuentas propias en el cliente (espejo de backend/app/contabilidad.py).
// Regla: TODO movimiento tiene dirección (entra o sale) y mueve el saldo; lo que cambia es si
// cuenta como ingreso/gasto en los informes. Un traslado propio es neutral; una transferencia
// a/de un tercero es un gasto/ingreso real.

export const MARCA_POSIBLE_TRASLADO = 'posible_traslado_propio' // la deja el lector del extracto
export const MARCA_NO_TRASLADO = 'no_es_traslado' // la deja el usuario: "es un gasto/ingreso real"
export const CATEGORIA_TRASLADO = 'Transferencia' // categoría neutral (no confundir con 'Transferencias' = tercero)

function sinAcentos(t) {
  return (t || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
}

// 'income' | 'expense' | null. Las dos patas de un traslado de la app son tipo 'transfer' con la
// dirección en notas (':in' entra, ':out' sale); un 'transfer' heredado sin dirección da null.
export function direccionDe(m) {
  if (m.tipo === 'income' || m.tipo === 'expense') return m.tipo
  const n = m.notas || ''
  if (m.fuente === 'transferencia_interna') return n.endsWith(':in') ? 'income' : n.endsWith(':out') ? 'expense' : null
  return null
}

export function signoDe(m) {
  const d = direccionDe(m)
  return d === 'income' ? '+' : d === 'expense' ? '-' : ''
}

export function esTrasladoConfirmado(m) {
  return m.fuente === 'transferencia_interna' || sinAcentos(m.categoria).trim().toLowerCase() === 'transferencia'
}

export function esPosibleTraslado(m) {
  const n = m.notas || ''
  return !esTrasladoConfirmado(m) && n.includes(MARCA_POSIBLE_TRASLADO) && !n.includes(MARCA_NO_TRASLADO)
}

// Etiqueta corta para filas y detalle, o null si es un ingreso/gasto normal.
export function etiquetaTraslado(m) {
  if (esTrasladoConfirmado(m)) return 'Traslado ↔'
  if (esPosibleTraslado(m)) return 'Posible traslado ↔'
  return null
}

// Texto del campo "Tipo" del detalle.
export function etiquetaTipo(m) {
  const d = direccionDe(m)
  const sentido = d === 'income' ? 'entra' : d === 'expense' ? 'sale' : ''
  const tr = etiquetaTraslado(m)
  if (tr) return sentido ? `${tr} (${sentido})` : tr
  return d === 'income' ? 'Ingreso' : d === 'expense' ? 'Gasto' : 'Movimiento'
}

function sinMarca(notas, marca) {
  return (notas || '')
    .split(' · ')
    .filter((p) => p && p !== marca)
    .join(' · ')
}

// Cambios para "Marcar como traslado entre mis cuentas".
export function cambiosMarcarTraslado(m) {
  return { categoria: CATEGORIA_TRASLADO, notas: sinMarca(m.notas, MARCA_NO_TRASLADO) }
}

// Cambios para "Es un gasto/ingreso real": ya no se empareja ni cuenta como traslado.
export function cambiosEsReal(m) {
  const base = sinMarca(sinMarca(m.notas, MARCA_POSIBLE_TRASLADO), MARCA_NO_TRASLADO)
  const cambios = { notas: base ? `${base} · ${MARCA_NO_TRASLADO}` : MARCA_NO_TRASLADO }
  if (esTrasladoConfirmado(m)) cambios.categoria = 'Otros'
  return cambios
}

const DOS_DIAS = 2 * 86400 * 1000

// Posibles contrapartes de `m` entre `otros`: dirección opuesta, mismo monto, otra cuenta,
// a <= 2 días, sin traslado ya confirmado. La más cercana en fecha primero.
export function candidatosContraparte(m, otros) {
  const d = direccionDe(m)
  if (!d) return []
  const t = new Date(m.fecha).getTime()
  return otros
    .filter(
      (o) =>
        o.id !== m.id &&
        o.cuenta_id !== m.cuenta_id &&
        direccionDe(o) === (d === 'income' ? 'expense' : 'income') &&
        Math.abs(o.monto - m.monto) < 1 &&
        Math.abs(new Date(o.fecha).getTime() - t) <= DOS_DIAS &&
        !esTrasladoConfirmado(o)
    )
    .sort((a, b) => Math.abs(new Date(a.fecha) - t) - Math.abs(new Date(b.fecha) - t))
}
