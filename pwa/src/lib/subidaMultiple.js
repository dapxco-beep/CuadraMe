// Lógica de la subida de VARIOS extractos a la vez (PDF, Excel, CSV), separada de la
// interfaz para poder probarla: validación, cola secuencial que aguanta fallos,
// normalización de lo que devuelve cada endpoint y deduplicación entre archivos.
import { claveComercio } from './comercio'

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
  return hit?.id || porDefecto || cuentas[0]?.id || ''
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
      estado: m.estado === 'faltante' ? 'nuevo' : 'ya',
    }))
  return {
    banco: r.banco_detectado || 'desconocido',
    periodo: r.periodo_desde ? { desde: r.periodo_desde, hasta: r.periodo_hasta } : periodoDe(items),
    items,
    historialId: r.historial_id,
    autoImportados: r.auto_importados || 0,
  }
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
    estado: p.estado === 'duplicado' ? 'ya' : p.estado === 'posible_duplicado' ? 'posible' : 'nuevo',
  }))
  return { banco: 'Excel / CSV', periodo: periodoDe(items), items }
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
    for (const it of a.items) if (it.estado === 'nuevo') claves.push(`${a.id}:${it.k}`)
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
