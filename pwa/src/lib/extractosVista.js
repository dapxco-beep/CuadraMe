// Reglas puras de la lista «Todos los extractos» (sin React, fáciles de probar).
// El servidor (app/estado_traer.py + app/extractos_vista.py) ya trae cada fila con su título
// («Nu Colombia · Cuenta · Julio 2026»), estado, frase de resultado, motivo y acciones.
// Aquí solo se filtra, se busca y se agrupa por mes.

// Estados de la lista, en el orden en que se ofrecen como filtro. El color nunca va solo: ícono + texto.
export const ESTADOS_VISTA = [
  { id: 'por_revisar', texto: 'Por revisar', plural: 'por revisar', clase: 'text-accent', fondo: 'bg-accent-soft' },
  { id: 'necesita_clave', texto: 'Necesita clave', plural: 'con clave pendiente', clase: 'text-accent', fondo: 'bg-accent-soft' },
  { id: 'no_se_pudo_leer', texto: 'No se pudo leer', plural: 'con error', clase: 'text-danger', fondo: 'bg-danger-soft' },
  { id: 'sin_procesar', texto: 'Sin procesar', plural: 'sin procesar', clase: 'text-ink-soft', fondo: 'bg-paper' },
  { id: 'revisado', texto: 'Revisado', plural: 'revisados', clase: 'text-cuadra', fondo: 'bg-cuadra-soft' },
  { id: 'anterior_al_inicio', texto: 'Anterior a tu fecha de inicio', plural: 'anteriores al inicio', clase: 'text-ink-soft', fondo: 'bg-paper' },
]

export const estadoVista = (id) => ESTADOS_VISTA.find((e) => e.id === id) || ESTADOS_VISTA[3]

// Qué filtro abre cada tarea de «Por hacer» (la tarea cuenta por revisar + sin procesar juntos).
export const FILTRO_DE_TAREA = {
  extractos_por_conciliar: ['por_revisar', 'sin_procesar'],
  falta_clave: ['necesita_clave'],
  extractos_sin_leer: ['no_se_pudo_leer'],
}

export const sinAcentos = (t) => String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()

// Lo que se busca en «julio», «nu», «tarjeta», «2026-07»... contra mes, título, banco y cuenta.
export function coincideBusqueda(it, texto) {
  const q = sinAcentos(texto)
  if (!q) return true
  const pajar = sinAcentos(`${it.titulo} ${it.mes_etiqueta} ${it.mes || ''} ${it.banco || ''} ${it.cuenta || ''} ${it.estado_etiqueta || ''}`)
  return q.split(/\s+/).every((p) => pajar.includes(p))
}

// Clave de la cuenta/banco por la que se filtra: la cuenta si la hay; si no, el banco.
export const claveCuenta = (it) => (it.cuenta_id ? `c:${it.cuenta_id}` : `b:${sinAcentos(it.banco) || 'sin-banco'}`)
export const nombreCuentaFiltro = (it) => it.cuenta || it.banco || 'Banco sin identificar'

export function opcionesCuenta(items) {
  const m = new Map()
  for (const it of items || []) if (!m.has(claveCuenta(it))) m.set(claveCuenta(it), nombreCuentaFiltro(it))
  return [...m.entries()].map(([id, nombre]) => ({ id, nombre })).sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
}

// filtro: { estados: [] (vacío = todos), cuenta: '' , mes: '' (AAAA-MM), texto: '' }
export function filtrar(items, { estados = [], cuenta = '', mes = '', texto = '' } = {}) {
  return (items || []).filter((it) => (
    (!estados.length || estados.includes(it.estado_vista))
    && (!cuenta || claveCuenta(it) === cuenta)
    && (!mes || it.mes === mes)
    && coincideBusqueda(it, texto)
  ))
}

// [{ mes: '2026-07' | null, etiqueta: 'Julio 2026' | 'Mes por confirmar', items }] del más reciente al más antiguo.
export function agruparPorMes(items) {
  const grupos = new Map()
  for (const it of items || []) {
    const k = it.mes || ''
    if (!grupos.has(k)) grupos.set(k, [])
    grupos.get(k).push(it)
  }
  return [...grupos.entries()]
    .sort(([a], [b]) => (a === '' ? 1 : b === '' ? -1 : b.localeCompare(a)))
    .map(([mes, lista]) => ({ mes: mes || null, etiqueta: lista[0].mes_etiqueta || 'Mes por confirmar', items: lista }))
}

// «6 revisados · 3 con clave pendiente...» a partir de los contadores (si el servidor no mandó la frase).
export function textoContadores(contadores) {
  const c = contadores || {}
  const partes = ['revisado', 'por_revisar', 'necesita_clave', 'sin_procesar', 'no_se_pudo_leer', 'anterior_al_inicio']
    .filter((k) => c[k])
    .map((k) => {
      const n = c[k]
      return {
        revisado: `${n} ${n === 1 ? 'revisado' : 'revisados'}`,
        por_revisar: `${n} por revisar`,
        necesita_clave: `${n} con clave pendiente`,
        sin_procesar: `${n} sin procesar`,
        no_se_pudo_leer: `${n} con error`,
        anterior_al_inicio: `${n} ${n === 1 ? 'anterior al inicio' : 'anteriores al inicio'}`,
      }[k]
    })
  return partes.join(' · ')
}

// Texto del botón de cada acción que manda el servidor (verbo primero, ≤ 3 palabras).
export const TEXTO_ACCION = {
  revisar: 'Revisar',
  ver: 'Ver qué pasó',
  revisar_de_nuevo: 'Revisar de nuevo',
  poner_clave: 'Poner clave',
  probar_clave: 'Probar la clave',
  intentar_de_nuevo: 'Intentar de nuevo',
  subir_de_nuevo: 'Subir de nuevo',
  reintentar: 'Reintentar',
  quitar_de_la_lista: 'Quitar de la lista',
  mi_banco_no_esta: 'Mi banco no está',
  cambiar_cuenta: 'Cambiar de cuenta',
}

// El texto de un botón según la fila: un grupo de errores por clave dice «Poner la clave» (una sola vez para todos) y
// un extracto sin banco identificado dice «Decirme de qué banco es» (no «Mi banco no está», que no explica nada).
export function textoAccion(accion, it = {}) {
  if (accion === 'poner_clave' && (it.copias || 1) > 1) return 'Poner la clave'
  if (accion === 'mi_banco_no_esta' && it.banco_sin_identificar) return 'Decirme de qué banco es'
  return TEXTO_ACCION[accion] || accion
}

// 'AAAA-MM' de «hoy» menos n meses (para el tope del selector de mes).
export function mesActual(hoy = new Date()) {
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`
}
