import { api } from './api'

// Textos y reglas puras de la pantalla Sincronización (sin React, fáciles de probar).

// Estado de una celda cuenta x mes -> cómo se dice y se pinta.
// El color nunca va solo: cada estado trae símbolo y texto.
export const ESTADOS_CELDA = {
  conciliado: { simbolo: '✓', texto: 'Conciliado', clase: 'bg-cuadra-soft text-cuadra border-cuadra/30' },
  extracto_pendiente: { simbolo: '⚠', texto: 'Por conciliar', clase: 'bg-accent-soft text-accent border-accent/40' },
  falta_clave: { simbolo: '🔑', texto: 'Falta la clave', clase: 'bg-danger-soft text-danger border-danger/40' },
  sin_extracto: { simbolo: '—', texto: 'Sin extracto', clase: 'bg-paper-raised text-ink-soft border-line' },
  vacio: { simbolo: '·', texto: 'Sin datos', clase: 'bg-transparent text-ink-soft/50 border-transparent' },
}

export function estadoCelda(estado) {
  return ESTADOS_CELDA[estado] || ESTADOS_CELDA.vacio
}

// Frase de una línea para el encabezado: 'Todo al día' o 'Tienes 4 cosas por resolver'.
export function resumenTareas(tareas) {
  const n = (tareas || []).length
  if (n === 0) return 'Todo al día'
  return `Tienes ${n} ${n === 1 ? 'cosa' : 'cosas'} por resolver`
}

// Un extracto ya conciliado (por Gmail o porque ese periodo se concilió por otro lado)
// nunca es pendiente: se muestra aparte, plegado, y no cuenta en las tareas.
export const ESTADOS_CONCILIADO = ['procesado', 'ya_conciliado']
export const esConciliado = (ex) => ESTADOS_CONCILIADO.includes(ex?.estado)

// { pendientes, conciliados }: lo que hay que atender y lo que ya quedó listo.
export function separarExtractos(lista) {
  const todos = Array.isArray(lista) ? lista : []
  return { pendientes: todos.filter((e) => !esConciliado(e)), conciliados: todos.filter(esConciliado) }
}

export function textoCruzados(n) {
  return `${n} ${n === 1 ? 'movimiento cruzado' : 'movimientos cruzados'}`
}

// Estado de un extracto de Gmail dicho en palabras.
export function textoEstadoExtracto(ex) {
  switch (ex?.estado) {
    case 'procesado':
    case 'ya_conciliado':
      return ex.cruzados != null ? `Conciliado · ${textoCruzados(ex.cruzados)}` : 'Conciliado'
    case 'nuevo':
      return 'Nuevo · listo para conciliar'
    case 'falta_clave':
      return 'Falta la clave del PDF'
    case 'descartado':
      return 'Ignorado'
    case 'error':
      return 'No se pudo leer el PDF'
    default:
      return ''
  }
}

export const BANCO_SIN_IDENTIFICAR = 'Banco sin identificar'

// Agrupa los extractos por banco (los sin banco, juntos al final), manteniendo el orden recibido.
export function agruparPorBanco(extractos) {
  const grupos = new Map()
  for (const ex of extractos || []) {
    const banco = ex.banco || BANCO_SIN_IDENTIFICAR
    if (!grupos.has(banco)) grupos.set(banco, [])
    grupos.get(banco).push(ex)
  }
  const lista = [...grupos.entries()].map(([banco, items]) => ({ banco, items }))
  return [...lista.filter((g) => g.banco !== BANCO_SIN_IDENTIFICAR), ...lista.filter((g) => g.banco === BANCO_SIN_IDENTIFICAR)]
}

// "21 de junio"-style no hace falta: la celda dice 'jun 26'. Nombre largo para el detalle.
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
export function nombreMes(clave) {
  const [a, m] = String(clave || '').split('-').map(Number)
  return a && m ? `${MESES[m - 1]} ${a}` : ''
}

const TIPOS_CUENTA = { ahorro: 'Ahorros', efectivo: 'Efectivo', credito: 'Crédito', inversion: 'Inversión' }

// Nombre para la cuadrícula: si dos cuentas se llaman igual se les agrega su tipo (y los
// últimos dígitos / alias de la tarjeta si lo tienen) para poder distinguirlas.
// `filas` = cuentas de GET /sincronizacion/estado; `cuentas` = las del contexto (traen tipo y alias).
export function nombresDesambiguados(filas, cuentas = []) {
  const cuenta = (id) => cuentas.find((c) => c.id === id) || {}
  const veces = {}
  for (const f of filas || []) veces[f.nombre] = (veces[f.nombre] || 0) + 1
  const salida = {}
  const usados = {}
  for (const f of filas || []) {
    if (veces[f.nombre] < 2) {
      salida[f.id] = f.nombre
      continue
    }
    const c = cuenta(f.id)
    const partes = [TIPOS_CUENTA[c.tipo] || c.tipo, c.alias_tarjeta ? `••${String(c.alias_tarjeta).slice(-4)}` : ''].filter(Boolean)
    let nombre = partes.length ? `${f.nombre} (${partes.join(' ')})` : f.nombre
    usados[nombre] = (usados[nombre] || 0) + 1
    if (usados[nombre] > 1) nombre = `${nombre} #${usados[nombre]}` // mismo tipo y sin alias: al menos un número
    salida[f.id] = nombre
  }
  return salida
}

// Mes anterior / siguiente de una clave 'YYYY-MM'.
export function moverMes(clave, delta) {
  const [a, m] = String(clave).split('-').map(Number)
  const t = a * 12 + (m - 1) + delta
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, '0')}`
}

// Conciliar un extracto de Gmail: nunca sin cuenta elegida. Devuelve { ok, error, historialId }
// (Correos y Sincronización usan esta misma función; el flujo de conciliación no cambia).
export async function conciliarExtracto(ex, cuentaId) {
  if (!cuentaId) return { ok: false, error: 'Elige la cuenta del extracto' }
  const r = await api.conciliarExtractoCorreo(ex.id, cuentaId)
  return r?.ok ? { ok: true, historialId: r.historial_id } : { ok: false, error: r?.error || 'No se pudo conciliar el extracto' }
}
