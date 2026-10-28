// Cierre de mes como asistente de 4 pasos. Puro (sin React) y probado en test/cierre_asistente.test.js.
//   1. ¿Cuadran tus cuentas?   (contra los extractos: GET /cierre-mes/extractos)
//   2. ¿Todo tiene categoría?  (cola de comercios sin categoría)
//   3. Revisa lo raro          (comisiones y posibles cobros duplicados)
//   4. Tu resumen del mes      (el cierre en sí)
// Cada paso dice en una frase cómo va (`estado` + `resumen`). «Listo para cerrar» = los 3 primeros sin pendientes.

export const PASOS = [
  { id: 'cuentas', corto: 'Cuentas', titulo: '¿Cuadran tus cuentas?' },
  { id: 'categorias', corto: 'Categorías', titulo: '¿Todo tiene categoría?' },
  { id: 'raro', corto: 'Lo raro', titulo: 'Revisa lo raro' },
  { id: 'resumen', corto: 'Resumen', titulo: 'Tu resumen del mes' },
]

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`

/** Las cuentas de todos los bancos en una sola lista. */
export function cuentasDelCierre(ext) {
  return (ext?.bancos || []).flatMap((b) => b.cuentas || [])
}

// El efectivo y las inversiones (un CDT) no mandan un extracto cada mes: que «falte» no es un pendiente del cierre.
const SIN_EXTRACTO_MENSUAL = ['efectivo', 'inversion']

function pasoCuentas(ext) {
  if (ext === null || ext === undefined) return { estado: 'cargando', resumen: 'Mirando tus cuentas…' }
  if (ext === false) return { estado: 'neutro', resumen: 'No pude comparar con tus extractos ahora. Puedes seguir.' }
  if (!ext.hay_datos) return { estado: 'neutro', resumen: 'Aún no hay movimientos de este mes para comparar.' }
  const cs = cuentasDelCierre(ext)
  const noCuadran = cs.filter((c) => c.estado === 'no_cuadra').length
  const sinExtracto = cs.filter((c) => c.estado === 'sin_extracto' && !SIN_EXTRACTO_MENSUAL.includes(c.tipo)).length
  if (noCuadran) return { estado: 'atencion', resumen: `${plural(noCuadran, 'cuenta no cuadra', 'cuentas no cuadran')} con tu banco.`, cantidad: noCuadran }
  if (sinExtracto) return { estado: 'atencion', resumen: `Falta el extracto de ${plural(sinExtracto, 'cuenta', 'cuentas')}.`, cantidad: sinExtracto }
  return { estado: 'ok', resumen: 'Todas tus cuentas cuadran con el banco.' }
}

function pasoCategorias(porCategorizar) {
  if (porCategorizar === null || porCategorizar === undefined) return { estado: 'cargando', resumen: 'Mirando tus categorías…' }
  const n = Number(porCategorizar) || 0
  if (n > 0) return { estado: 'atencion', resumen: `${plural(n, 'comercio sin categoría', 'comercios sin categoría')}.`, cantidad: n }
  return { estado: 'ok', resumen: 'Todo tiene su categoría.' }
}

/** Cantidad de cosas raras que detectó el servidor (comisiones y cobros duplicados). */
export function cosasRaras(alertas) {
  return [
    ...(alertas?.comisiones || []).map((c) => ({ tipo: 'comision', clave: `c-${c.descripcion}`, ...c })),
    ...(alertas?.cobros_duplicados || []).map((d) => ({ tipo: 'duplicado', clave: `d-${d.movimiento_id_1}`, ...d })),
  ]
}

function pasoRaro(alertas) {
  if (alertas === null || alertas === undefined) return { estado: 'cargando', resumen: 'Buscando cosas raras…' }
  if (alertas === false) return { estado: 'neutro', resumen: 'No pude buscar cosas raras ahora. Puedes seguir.' }
  const n = cosasRaras(alertas).length
  if (n > 0) return { estado: 'atencion', resumen: `${plural(n, 'cosa para mirar', 'cosas para mirar')}.`, cantidad: n }
  return { estado: 'ok', resumen: 'No encontré nada raro.' }
}

function pasoResumen(informe) {
  if (informe) return { estado: 'ok', resumen: 'El cierre de este mes ya está listo.' }
  return { estado: 'neutro', resumen: 'Aún no lo has generado.' }
}

/** Los 4 pasos con su estado: { id, corto, titulo, estado: 'ok'|'atencion'|'cargando'|'neutro', resumen, cantidad? }. */
export function estadoPasos({ ext, porCategorizar, alertas, informe } = {}) {
  const por = {
    cuentas: pasoCuentas(ext),
    categorias: pasoCategorias(porCategorizar),
    raro: pasoRaro(alertas),
    resumen: pasoResumen(informe),
  }
  return PASOS.map((p) => ({ ...p, ...por[p.id] }))
}

/** Pasos que piden atención antes de cerrar (los 3 primeros). */
export const pendientesDeCierre = (pasos) => (pasos || []).slice(0, 3).filter((p) => p.estado === 'atencion')

/** Listo para cerrar: ya cargó todo y no queda nada que pida atención. */
export function listoParaCerrar(pasos) {
  const primeros = (pasos || []).slice(0, 3)
  return primeros.length === 3 && primeros.every((p) => p.estado !== 'cargando') && pendientesDeCierre(pasos).length === 0
}

/** «Paso 2 de 4 · 1 por resolver». */
export function textoAvance(indice, pasos) {
  const k = pendientesDeCierre(pasos).length
  return `Paso ${indice + 1} de ${PASOS.length}${k ? ` · ${k} por resolver` : ''}`
}
