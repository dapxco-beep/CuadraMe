// Ayudas puras del «Cuadre con el banco» (el cálculo vive en el servidor: app/cuadre_extracto.py).
export const ORIENTACION = 'Orientación: el saldo oficial es el de tu banco.'

// Líneas «nuevas» marcadas de un archivo: cuentan en el cuadre como si ya estuvieran traídas.
export function lineasPorImportar(items = [], seleccion = new Set(), archivoId = '') {
  return items
    .filter((it) => (it.estado === 'nuevo' || it.estado === 'posible') && seleccion.has(`${archivoId}:${it.k}`))
    .map((it) => ({ fecha: it.fecha, monto: it.monto, tipo: it.tipo }))
}

// Cuerpo de POST /conciliacion/cuadre/evaluar. En PDF el servidor ya guardó los saldos en el historial;
// en Excel/CSV viajan los que se leyeron del archivo (o los que la persona escribió).
export function cuerpoEvaluar({ cuentaId, historialId, saldos, manual, porImportar = [], avisoCuenta, registrar = false }) {
  const s = { ...(saldos || {}), ...(manual || {}) }
  const cuerpo = { cuenta_id: cuentaId, por_importar: porImportar, registrar }
  if (historialId) cuerpo.historial_id = historialId
  if (!historialId || manual) {
    if (s.saldo_final != null) cuerpo.saldo_final = s.saldo_final
    if (s.saldo_inicial != null) cuerpo.saldo_inicial = s.saldo_inicial
    if (s.fecha_corte) cuerpo.fecha_corte = s.fecha_corte
    if (s.periodo_inicio) cuerpo.periodo_inicio = s.periodo_inicio
    if (s.moneda) cuerpo.moneda = s.moneda
  }
  if (avisoCuenta) cuerpo.aviso_cuenta = avisoCuenta
  return cuerpo
}

// Un mes en pocas palabras, sin color como único aviso.
export function textoEstadoMes(m) {
  if (m.dejo_de_cuadrar) return 'Dejó de cuadrar'
  if (m.estado === 'cuadra') return 'Cuadra'
  if (m.estado === 'diferencia') return 'Con diferencia'
  if (m.estado === 'antes_de_inicio') return 'Antes de tu inicio'
  return 'Sin extracto'
}

// El cliente de la API ya traduce el mensaje; el código del 409 viene en err.detalle.codigo.
export function mensajeError(err, porDefecto = 'No pudimos hacerlo. Revisa tu conexión e intenta de nuevo.') {
  return err?.message || porDefecto
}
export const codigoError = (err) => err?.detalle?.codigo || null
