// Lógica de la subida de VARIOS extractos a la vez (PDF, Excel, CSV), separada de la
// interfaz para poder probarla: validación, cola secuencial que aguanta fallos,
// normalización de lo que devuelve cada endpoint y deduplicación entre archivos.
import { claveComercio } from './comercio'
import { cuentaRecordada, esCredito, marcaDe, productoDeTexto } from './cuentasBanco'
import { formatCOP } from './format'

export const MAX_ARCHIVOS = 10
export const MAX_BYTES_PDF = 15 * 1024 * 1024 // igual que el servidor (~15 MB decodificado)
export const MAX_BYTES_TABULAR = 5 * 1024 * 1024
const EXT_TABULAR = ['csv', 'txt', 'xlsx', 'xls']

export function tipoDeArchivo(nombre) {
  const ext = (nombre || '').toLowerCase().split('.').pop()
  if (ext === 'pdf') return 'pdf'
  if (EXT_TABULAR.includes(ext)) return 'tabular'
  return null
}

/** Separa lo que se puede procesar de lo que no, con el motivo legible. */
export function validarSeleccion(archivos, yaAgregados = 0) {
  const aceptados = []
  const rechazados = []
  for (const f of archivos) {
    const tipo = tipoDeArchivo(f.name)
    if (!tipo) rechazados.push({ nombre: f.name, motivo: 'Formato no soportado: sube PDF, Excel (.xlsx, .xls) o CSV.' })
    else if (f.size > (tipo === 'pdf' ? MAX_BYTES_PDF : MAX_BYTES_TABULAR)) {
      rechazados.push({ nombre: f.name, motivo: `Pesa más de ${tipo === 'pdf' ? 15 : 5} MB.` })
    } else if (yaAgregados + aceptados.length >= MAX_ARCHIVOS) {
      rechazados.push({ nombre: f.name, motivo: `Máximo ${MAX_ARCHIVOS} archivos a la vez.` })
    } else aceptados.push(f)
  }
  return { aceptados, rechazados }
}

const sinTildes = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

/** Cuenta sugerida: la que nombra el archivo ('extracto_nequi_sep.pdf' -> Nequi); si no, la por defecto. */
export function sugerirCuenta(nombreArchivo, cuentas, porDefecto = '') {
  const n = sinTildes(nombreArchivo)
  const hit = cuentas.find((c) => {
    const nombre = sinTildes(c.nombre)
    return nombre.length >= 3 && n.includes(nombre)
  })
  if (hit) return hit.id
  // Banco con varias cuentas ('extracto_nu_tarjeta.pdf' con «Nu Colombia» y «Nu Tarjeta»):
  // el tipo que insinúa el nombre del archivo, o lo que la persona eligió antes para ese banco.
  const delBanco = cuentas.filter((c) => marcaDe(c.nombre).some((w) => n.split(/[^a-z0-9]+/).includes(w)))
  if (delBanco.length > 1) {
    const producto = productoDeTexto(nombreArchivo)
    const deTipo = producto ? delBanco.filter((c) => esCredito(c) === (producto === 'credito')) : delBanco
    if (deTipo.length === 1) return deTipo[0].id
    const recordada = cuentaRecordada(delBanco[0].nombre, producto, cuentas)
    if (recordada && delBanco.some((c) => c.id === recordada)) return recordada
  } else if (delBanco.length === 1) {
    return delBanco[0].id
  }
  return porDefecto || cuentas[0]?.id || ''
}

/** 'dd/mm/aaaa', 'dd-mm-aaaa' o ISO -> 'aaaa-mm-dd' (o '' si no se entiende). */
export function fechaISO(valor) {
  const s = String(valor || '').trim()
  let m = /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/.exec(s)
  if (m) return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`
  m = /^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})/.exec(s)
  if (m) {
    const anio = m[3].length === 2 ? `20${m[3]}` : m[3]
    return `${anio}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`
  }
  return ''
}

/** Mismo movimiento en dos archivos: misma cuenta, día, monto, tipo y comercio. */
export function claveDedup(cuentaId, item) {
  return [cuentaId, fechaISO(item.fecha), Math.round(Number(item.monto) * 100), item.tipo, claveComercio(item.descripcion)].join('|')
}

function periodoDe(items) {
  const fechas = items.map((i) => fechaISO(i.fecha)).filter(Boolean).sort()
  return fechas.length ? { desde: fechas[0], hasta: fechas[fechas.length - 1] } : null
}

/** Respuesta de POST /conciliacion/procesar -> estructura común. */
export function normalizarPdf(r) {
  const items = (r.review || [])
    .filter((m) => m.estado !== 'sobrante')
    .map((m) => ({
      k: m.fingerprint,
      fp: m.fingerprint,
      fecha: m.fecha,
      descripcion: m.descripcion,
      monto: m.monto,
      tipo: m.tipo,
      categoria: m.categoria_sugerida || 'Otros',
      razon: m.razon_categoria || null,
      confianza: typeof m.confianza_categoria === 'number' ? m.confianza_categoria : null,
      // 'anterior': antes de la fecha de inicio (punto de partida): no se ofrece ni se importa.
      // 'dudoso': parece algo que ya tienes pero no es idéntico; la persona decide (dos filas lado a lado).
      estado: m.estado === 'faltante' || m.estado === 'corregir_monto' || m.estado === 'quitar_repetido' ? 'nuevo' : m.estado === 'anterior' ? 'anterior'
        : m.estado === 'aproximado' && m.descripcion_registrada ? 'dudoso' : 'ya',
      registrado: m.estado === 'aproximado' && m.descripcion_registrada
        ? { descripcion: m.descripcion_registrada, monto: m.monto_registrado, fecha: m.fecha_registrada } : null,
      matchId: m.match_id || null,
      // Línea con varios montos: no se marca ni se importa hasta que la persona elige el monto (ver textoLineaDudosa).
      dudosa: Boolean(m.lectura_dudosa),
      montosAlt: Array.isArray(m.montos_alternativos) ? m.montos_alternativos : [],
      // «Pago ...» de un extracto de tarjeta: se sugiere como traslado entre tus cuentas, no como un gasto.
      pagoTarjeta: Boolean(m.pago_tarjeta),
      // «Pago $A» de la tarjeta: la fila importable es por A; aquí va cómo se aplicó (capital, intereses, cargos, B y C).
      pagoDetalle: m.pago_detalle || null,
      // Compra en cuotas: lo que falta por pagar de la compra.
      restante: typeof m.restante === 'number' && m.restante > 0 ? m.restante : null,
      cuotas: m.cuotas || null,
      avisoLinea: m.aviso_linea || null,
      // Corrige un movimiento ya importado con la lectura vieja (el lector lo declara): no crea otro movimiento.
      correccion: m.estado === 'corregir_monto'
        ? { tipo: 'corregir', anterior: m.monto_anterior ?? null }
        : m.estado === 'quitar_repetido' ? { tipo: 'quitar', correcto: m.monto_correcto ?? null } : null,
      apagada: m.marcar_por_defecto === false, // sin certeza: la casilla queda apagada hasta que la persona confirme
    }))
  const filaInfo = (m) => ({
    descripcion: m.descripcion,
    fecha: m.fecha,
    monto: m.monto,
    montoRegistrado: m.monto_registrado ?? null,
    descripcionRegistrada: m.descripcion_registrada || null,
    categoria: m.categoria_sugerida || null,
  })
  return {
    banco: r.banco_detectado || 'desconocido',
    periodo: r.periodo_desde ? { desde: r.periodo_desde, hasta: r.periodo_hasta } : periodoDe(items),
    items,
    anteriores: items.filter((i) => i.estado === 'anterior').length,
    historialId: r.historial_id,
    autoImportados: r.auto_importados || 0,
    yaConciliado: r.ya_conciliado || null,
    // Lo que el lector no pudo leer con certeza (se avisa) y lo que cruzó con tu registro rápido.
    descartados: r.descartados || 0,
    // Extracto de la tarjeta de Nu: ¿lo leído suma lo que dice el extracto? y los datos del resumen de la página 1.
    mensajeLectura: r.mensaje_lectura || null,
    lecturaCompleta: r.lectura_completa ?? null,
    resumenTarjeta: r.resumen_tarjeta || null,
    completados: (r.review || []).filter((m) => m.estado === 'completado').map(filaInfo),
    sobrantes: (r.review || []).filter((m) => m.estado === 'sobrante').map(filaInfo),
    propuestaTarjeta: r.propuesta_tarjeta || null,
    saldosExtracto: r.saldos_extracto || null, // saldos que imprime el extracto (para cuadrar con el banco)
    avisoCuenta: r.aviso_cuenta || null, // el PDF parece de otro producto del mismo banco (tarjeta vs ahorros)
    origen: r.origen || null, // de dónde salió el extracto y a qué cuenta quedó (al reabrir una revisión)
  }
}

/** Texto del aviso de líneas que no se pudieron leer ('' si no hubo). */
export function textoDescartados(n) {
  if (!n) return ''
  return n === 1
    ? '1 línea no se pudo leer con certeza y no aparece aquí. Revisa tu extracto.'
    : `${n} líneas no se pudieron leer con certeza y no aparecen aquí. Revisa tu extracto.`
}

export const AVISO_LINEA_DOS_MONTOS = 'Esta línea trae dos montos. Elige el correcto'

/** Monto que se va a importar de una línea: el elegido por la persona si lo hay; si no, el que se leyó. */
export const montoDeLinea = (it, elegido) => (it?.dudosa && elegido != null ? Number(elegido) : it?.monto)

/** Una línea de lectura dudosa solo se puede importar con un monto elegido (>= 1). */
export const montoValido = (v) => Number.isFinite(Number(v)) && Number(v) >= 1

/** «Pago de tarjeta» / «Traslado entre tus cuentas»: lo que se sugiere de una línea «Pago ...». */
export const TEXTO_PAGO_TARJETA = 'Parece el pago de tu tarjeta desde otra cuenta tuya: se cuenta como traslado, no como gasto.'

/**
 * «Cómo se aplicó este pago: capital $x · intereses $y · cargos $z» y «Se aplicó $B y $C».
 * null si el pago no trae el detalle.
 */
export function textoPagoAplicado(d) {
  if (!d) return null
  const partes = [['capital', d.capital], ['intereses', d.intereses], ['cargos', d.cargos]].filter(([, v]) => typeof v === 'number')
  const aplicado = Array.isArray(d.aplicado) ? d.aplicado.filter((v) => typeof v === 'number') : []
  if (!partes.length && !aplicado.length) return null
  return {
    principal: partes.length ? `Cómo se aplicó este pago: ${partes.map(([k, v]) => `${k} ${formatCOP(v)}`).join(' · ')}` : 'Cómo se aplicó este pago',
    aplicado: aplicado.length ? `Se aplicó ${aplicado.map((v) => formatCOP(v)).join(' y ')}.` : null,
  }
}

const FECHA_CORTA = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
const fechaIso = (iso) => (iso ? FECHA_CORTA.format(new Date(`${iso}T00:00:00Z`)) : null)

/** Filas [etiqueta, valor] del resumen de la página 1 del extracto de la tarjeta (solo lo que se pudo leer). */
export function filasResumenTarjeta(r) {
  if (!r) return []
  const m = (v) => (typeof v === 'number' ? formatCOP(v) : null)
  const periodo = r.periodo?.inicio && r.periodo?.fin ? `${fechaIso(r.periodo.inicio)} a ${fechaIso(r.periodo.fin)}` : null
  return [
    ['Deuda a pagar este mes', m(r.deuda_a_pagar)],
    ['Pago mínimo', m(r.pago_minimo)],
    ['Fecha límite de pago', fechaIso(r.limite_pago)],
    ['Fecha de corte', fechaIso(r.corte)],
    ['Periodo facturado', periodo],
    ['Cupo', m(r.cupo)],
    ['Usado', m(r.usado)],
    ['Disponible', m(r.disponible)],
    ['Cuota de manejo', m(r.cuota_manejo)],
    ['Cargos por conversión', m(r.cargos_conversion)],
    ['Intereses', m(r.intereses)],
    ['Abonaste', m(r.abonaste)],
    ['Deuda restante', m(r.deuda_restante)],
  ].filter(([, v]) => v)
}

/** Interpreta lo que se escribe en el campo del monto: «697.534,97», «474542», «$ 474.542,00». null si no sirve. */
export function leerMontoEscrito(texto) {
  const limpio = String(texto ?? '').replace(/[^\d.,]/g, '')
  if (!limpio) return null
  const ultimoPunto = limpio.lastIndexOf('.')
  const ultimaComa = limpio.lastIndexOf(',')
  const decimal = Math.max(ultimoPunto, ultimaComa)
  let n
  if (decimal >= 0 && limpio.length - decimal - 1 <= 2 && limpio.length - decimal - 1 > 0) {
    n = Number(`${limpio.slice(0, decimal).replace(/[.,]/g, '')}.${limpio.slice(decimal + 1)}`)
  } else {
    n = Number(limpio.replace(/[.,]/g, ''))
  }
  return Number.isFinite(n) && n > 0 ? n : null
}

/** Claves únicas para React: dos filas idénticas el mismo día comparten huella (se importan juntas). */
export function clavesUnicas(items) {
  const vistas = new Map()
  return items.map((it) => {
    const n = vistas.get(it.k) || 0
    vistas.set(it.k, n + 1)
    return `${it.k}#${n}`
  })
}

/** Cuántas filas "nuevas" del archivo comparten esta huella (las gemelas se marcan juntas). */
export function gemelasNuevas(items, k) {
  return items.filter((it) => it.estado === 'nuevo' && it.k === k).length
}

/** Respuesta de POST /importar/vista-previa -> estructura común. */
export function normalizarTabular(r) {
  const items = (r.propuesta || []).map((p) => ({
    k: String(p.fila),
    fp: null,
    fecha: p.fecha,
    descripcion: p.descripcion,
    monto: p.monto,
    tipo: p.tipo,
    categoria: p.categoria || 'Otros',
    razon: p.razon_categoria || null,
    confianza: null,
    estado: p.estado === 'duplicado' ? 'ya'
      : p.estado === 'posible_duplicado' ? (p.registrado ? 'dudoso' : 'posible')
        : p.estado === 'anterior' ? 'anterior' : 'nuevo',
    registrado: p.registrado || null,
    matchId: p.match_id || null,
  }))
  return {
    banco: 'Excel / CSV',
    periodo: periodoDe(items),
    items,
    anteriores: items.filter((i) => i.estado === 'anterior').length,
    yaConciliado: r.ya_conciliado || null,
    descartados: r.resumen?.con_error || 0,
    saldosExtracto: r.saldos || null,
  }
}

/**
 * Procesa los archivos UNO TRAS OTRO. Un fallo (clave faltante, archivo dañado, error del
 * servidor) deja a ese archivo en error y la cola sigue con el siguiente.
 * procesarUno(archivo) devuelve un parche { estado: 'listo' | 'falta_clave' | 'error', ... } o lanza.
 * onCambio(id, parche) y onProgreso({ actual, total }) permiten pintar la interfaz.
 */
export async function procesarCola(archivos, procesarUno, { onCambio = () => {}, onProgreso = () => {} } = {}) {
  const pendientes = archivos.filter((a) => a.estado === 'pendiente')
  let actual = 0
  for (const a of pendientes) {
    actual += 1
    onProgreso({ actual, total: pendientes.length })
    onCambio(a.id, { estado: 'procesando', error: '' })
    try {
      const parche = await procesarUno(a)
      onCambio(a.id, parche)
    } catch (err) {
      onCambio(a.id, { estado: 'error', error: err?.message || 'No se pudo procesar el archivo' })
    }
  }
  onProgreso({ actual: 0, total: pendientes.length })
}

/**
 * Deduplica ENTRE archivos: si el mismo movimiento (misma cuenta, día, monto, tipo y comercio)
 * ya apareció en un archivo anterior, queda como 'repetido' y no se importa dos veces. Los
 * periodos que se solapan (p. ej. dos extractos del mismo mes) no duplican nada. Dentro de un
 * mismo archivo no se toca: dos compras iguales el mismo día son legítimas.
 */
export function consolidar(archivos) {
  const vistos = new Map() // clave -> { id, nombre } del primer archivo donde apareció
  let repetidos = 0
  const salida = archivos.map((a) => {
    if (a.estado !== 'listo') return a
    const propias = new Set()
    const items = a.items.map((it) => {
      const clave = claveDedup(a.cuentaId, it)
      const previo = vistos.get(clave)
      propias.add(clave)
      if (previo && previo.id !== a.id && it.estado !== 'ya') {
        repetidos += 1
        return { ...it, estado: 'repetido', repetidoDe: previo.nombre }
      }
      return it
    })
    propias.forEach((c) => {
      if (!vistos.has(c)) vistos.set(c, { id: a.id, nombre: a.nombre })
    })
    return { ...a, items }
  })
  return { archivos: salida, repetidos }
}

/** Claves 'archivoId:k' de todo lo que falta registrar (para "seleccionar todo lo que falta"). */
export function clavesFaltantes(archivos) {
  const claves = []
  for (const a of archivos) {
    if (a.estado !== 'listo') continue
    // Una línea de lectura dudosa nunca viene marcada de entrada: primero se elige su monto.
    for (const it of a.items) if (it.estado === 'nuevo' && !it.dudosa && !it.apagada) claves.push(`${a.id}:${it.k}`)
  }
  return claves
}

/** Agrupa por cuenta y, dentro, por archivo: [{ cuentaId, archivos: [...] }]. */
export function agruparPorCuenta(archivos) {
  const mapa = new Map()
  for (const a of archivos) {
    if (a.estado !== 'listo') continue
    if (!mapa.has(a.cuentaId)) mapa.set(a.cuentaId, [])
    mapa.get(a.cuentaId).push(a)
  }
  return [...mapa.entries()].map(([cuentaId, lista]) => ({ cuentaId, archivos: lista }))
}

/** Texto de estado de un archivo para la lista de la cola. */
export const ETIQUETA_ARCHIVO = {
  pendiente: 'En espera',
  procesando: 'Procesando…',
  listo: 'Listo',
  falta_clave: 'Falta la clave del PDF',
  error: 'No se pudo procesar',
}

/**
 * «Esto es lo que va a pasar» con un archivo: cuántas líneas coinciden con lo que ya tienes (no se
 * duplican), cuántas son nuevas y cuántas parecen duplicados dudosos. Pura, para poder probarla.
 */
export function resumenPrevio(items) {
  const lista = items || []
  const n = (...estados) => lista.filter((i) => estados.includes(i.estado)).length
  return {
    coinciden: n('ya', 'repetido'),
    nuevos: lista.filter((i) => ['nuevo', 'posible'].includes(i.estado) && !i.correccion).length,
    correcciones: lista.filter((i) => i.estado === 'nuevo' && i.correccion).length,
    dudosos: n('dudoso'),
    anteriores: n('anterior'),
  }
}

const pesos = (v) => `$${new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(v)}`
const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const diaMes = (iso) => {
  const [, m, d] = fechaISO(iso).split('-')
  return `${Number(d)} ${MESES_CORTOS[Number(m) - 1] || ''}`.trim()
}

/**
 * Texto de una línea de corrección (null si la línea no corrige nada):
 *  corregir: «Corrige tu pago del 5 oct: pasa de $B a $A (es lo que pagaste; $B y $C son cómo se aplicó)»
 *  quitar:   «Quitar el pago repetido de $B» (+ detalle: «Tienes dos pagos del 5 oct ($B y $A)»).
 */
export function textoCorreccion(it) {
  const c = it?.correccion
  if (!c) return null
  const dia = diaMes(it.fecha)
  if (c.tipo === 'quitar') {
    return {
      titulo: `Quitar el pago repetido de ${pesos(it.monto)}`,
      detalle: c.correcto != null ? `Tienes dos pagos del ${dia} (${pesos(it.monto)} y ${pesos(c.correcto)}). Queda el de ${pesos(c.correcto)}.` : null,
    }
  }
  const aplicado = Array.isArray(it.pagoDetalle?.aplicado) ? it.pagoDetalle.aplicado.filter((v) => typeof v === 'number') : []
  const como = aplicado.length ? ` (es lo que pagaste; ${aplicado.map(pesos).join(' y ')} son cómo se aplicó)` : ''
  return { titulo: `Corrige tu pago del ${dia}: pasa de ${pesos(c.anterior)} a ${pesos(it.monto)}${como}`, detalle: null }
}

export const textoCorrecciones = (n) => (n === 1 ? '1 corrección' : `${n} correcciones`)

/** Texto de una línea del resumen previo, sin jerga. */
export function textoPrevio({ coinciden, nuevos, dudosos }) {
  const partes = []
  partes.push(coinciden === 1 ? '1 coincide con lo que ya tienes (no se duplica)' : `${coinciden} coinciden con lo que ya tienes (no se duplican)`)
  partes.push(nuevos === 1 ? '1 es nuevo' : `${nuevos} son nuevos`)
  if (dudosos > 0) partes.push(dudosos === 1 ? '1 parece repetido y necesita tu ayuda' : `${dudosos} parecen repetidos y necesitan tu ayuda`)
  return partes
}
