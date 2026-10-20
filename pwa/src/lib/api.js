import { supabase } from './supabase'
import { borrarSeguridad } from './seguridad'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

import { MSG_ERROR_SERVIDOR, MSG_SESION_VENCIDA, MSG_SIN_CONEXION } from './mensajesBase'
import { mensajeAmable, mensajePorEstado } from './mensajes'
import { avisarConexionOk, avisarDatosGuardados, olvidarVistos, recordarVisto, vistoSinRed, activarVistos } from './ultimoVisto'

export { MSG_ERROR_SERVIDOR, MSG_SESION_VENCIDA, MSG_SIN_CONEXION }

// fetch() falla con un TypeError ("Failed to fetch", "Load failed", "NetworkError...")
// cuando no hay red o el servidor no responde. Ese texto en inglés no le sirve a nadie.
async function fetchSeguro(url, opciones) {
  try {
    return await fetch(url, opciones)
  } catch (e) {
    if (e?.name === 'AbortError') throw e
    const err = new Error(MSG_SIN_CONEXION)
    err.sinConexion = true
    throw err
  }
}

// Un 401 con sesión significa que el token ya no vale (venció o la revocaron):
// se cierra la sesión de forma limpia y se avisa, en vez de dejar la app a medias.
let cerrandoSesion = false
async function cerrarSesionVencida() {
  if (cerrandoSesion) return
  cerrandoSesion = true
  invalidarCache()
  olvidarVistos()
  try {
    borrarSeguridad()
    await supabase.auth.signOut()
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('cuadrame:sesion-vencida', { detail: { mensaje: MSG_SESION_VENCIDA } }))
    }
  } catch {
    // sin red el signOut puede fallar; el token ya no servía de todos modos
  } finally {
    cerrandoSesion = false
  }
}

// ── Deduplicación y caché de lecturas (GET) ─────────────────────────────────────────────
// Antes cada componente pedía lo suyo: Inicio disparaba ~33 peticiones (GET /cuentas x5, etc.)
// y con el backend lejos (150-250 ms de ida y vuelta) cada duplicado se nota.
//  - Dos GET idénticos al mismo tiempo comparten una sola petición.
//  - La respuesta se recuerda unos segundos (TTL).
//  - Cualquier escritura (POST/PUT/PATCH/DELETE) vacía la caché: se prefiere pedir de más a
//    mostrar un dato viejo. Una lectura que arrancó ANTES de la escritura no se guarda.
//  - La clave incluye al usuario: al cambiar de sesión no se mezclan datos.
//  - Se entrega una copia, así que quien reciba el dato puede modificarlo sin afectar a otros.
const TTL_CACHE_MS = 5000
let ttlCache = import.meta.env.MODE === 'test' ? 0 : TTL_CACHE_MS // las pruebas piden fresco salvo que activen la caché
let cacheActiva = true
const cacheLecturas = new Map() // clave -> { hasta, valor }
const lecturasEnVuelo = new Map() // clave -> Promise
let generacion = 0
const estadisticas = { red: 0, compartidas: 0, cacheadas: 0 }

export function invalidarCache() {
  cacheLecturas.clear()
  lecturasEnVuelo.clear()
  generacion++
}
// Solo para pruebas y mediciones.
export function configurarCache({ ttl, desactivar = false, vistos: conVistos } = {}) {
  ttlCache = ttl ?? TTL_CACHE_MS
  cacheActiva = !desactivar
  if (conVistos !== undefined) activarVistos(!!conVistos)
  invalidarCache()
}
export function estadisticasPeticiones(reiniciar = false) {
  const copia = { ...estadisticas }
  if (reiniciar) Object.assign(estadisticas, { red: 0, compartidas: 0, cacheadas: 0 })
  return copia
}
const copiar = (v) => (v !== null && typeof v === 'object' ? JSON.parse(JSON.stringify(v)) : v)

// Lecturas que index.html ya lanzó mientras bajaba el JS (ver el <script> de arranque). Se recogen UNA
// vez, solo si llegan de la misma sesión y hace menos de 15 s; si fallaron, se pide normalmente.
function recogerArranque(ruta, token) {
  try {
    const a = typeof window !== 'undefined' ? window.__arranque : null
    if (!a || !token || a.t !== token || Date.now() - a.en > 15000) return null
    const p = a.p[ruta]
    if (!p) return null
    delete a.p[ruta]
    return p.then((v) => (v === undefined ? pedir(ruta, {}) : v))
  } catch {
    return null
  }
}

async function request(path, opciones = {}) {
  const { method = 'GET', auth = true, sinCache = false } = opciones
  if (method !== 'GET') {
    invalidarCache()
    try {
      return await pedir(path, opciones)
    } finally {
      invalidarCache() // las lecturas lanzadas mientras escribía pudieron ver el estado viejo
    }
  }
  let uid = 'anon'
  let token = null
  if (auth) {
    const { data } = await supabase.auth.getSession()
    uid = data?.session?.user?.id || 'anon'
    token = data?.session?.access_token || null
  }
  if (sinCache || !cacheActiva) {
    estadisticas.red++
    return pedir(path, opciones)
  }
  const clave = `${uid}|${path}`
  const guardada = cacheLecturas.get(clave)
  if (guardada && guardada.hasta > Date.now()) {
    estadisticas.cacheadas++
    return copiar(guardada.valor)
  }
  const enVuelo = lecturasEnVuelo.get(clave)
  if (enVuelo) {
    estadisticas.compartidas++
    return enVuelo.then(copiar)
  }
  const gen = generacion
  estadisticas.red++
  const promesa = (recogerArranque(path, token) || pedir(path, opciones)).then(
    (valor) => {
      if (ttlCache > 0 && gen === generacion) cacheLecturas.set(clave, { hasta: Date.now() + ttlCache, valor })
      if (lecturasEnVuelo.get(clave) === promesa) lecturasEnVuelo.delete(clave)
      if (gen === generacion) recordarVisto(uid, path, valor)
      avisarConexionOk()
      return valor
    },
    (err) => {
      if (lecturasEnVuelo.get(clave) === promesa) lecturasEnVuelo.delete(clave)
      // Sin red: en vez de un error, lo último que se vio (y la app avisa que es una copia).
      if (err?.sinConexion) {
        const v = vistoSinRed(uid, path)
        if (v !== undefined) {
          avisarDatosGuardados()
          return v
        }
      }
      throw err
    }
  )
  lecturasEnVuelo.set(clave, promesa)
  return promesa.then(copiar)
}

async function pedir(path, { method = 'GET', body, auth = true, headers: extra } = {}) {
  // Un FormData (subida de archivo) lo arma el navegador con su propio Content-Type y límites.
  const esForm = typeof FormData !== 'undefined' && body instanceof FormData
  const headers = { ...(esForm ? {} : { 'Content-Type': 'application/json' }), ...(extra || {}) }
  let conSesion = false
  if (auth) {
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    if (token) {
      headers.Authorization = `Bearer ${token}`
      conSesion = true
    }
  }

  const res = await fetchSeguro(`${API_URL}${path}`, {
    method,
    headers,
    body: body ? (esForm ? body : JSON.stringify(body)) : undefined,
  })

  if (!res.ok) {
    if (res.status === 401 && conSesion) {
      await cerrarSesionVencida()
      const err = new Error(MSG_SESION_VENCIDA)
      err.status = 401
      throw err
    }
    const data = await res.json().catch(() => ({}))
    const d = data.detail
    if (res.status >= 500) {
      const err = new Error(MSG_ERROR_SERVIDOR)
      err.status = res.status
      err.detalle = d
      throw err
    }
    // Autorización pendiente (Ley 1581): el backend responde con un objeto {codigo, finalidad, mensaje}.
    // Se avisa a la app para que muestre el consentimiento específico en vez de un error crudo.
    if (d && typeof d === 'object' && d.codigo === 'consentimiento_requerido') {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('cuadrame:consentimiento', { detail: { finalidad: d.finalidad } }))
      }
      const err = new Error(d.mensaje || 'Falta una autorización')
      err.codigo = d.codigo
      err.finalidad = d.finalidad
      throw err
    }
    // detail puede ser texto, un objeto (409 con datos) o la lista de errores de validación.
    const mensaje =
      typeof d === 'string'
        ? d
        : Array.isArray(d)
          ? String(d[0]?.msg || '').replace(/^Value error, /, '')
          : d?.mensaje
    // Texto técnico del servidor («Not Found», «jwt expired»…) se traduce; si no dijo nada, va por código.
    const err = new Error(mensaje ? mensajeAmable(mensaje, { status: res.status }) : mensajePorEstado(res.status))
    err.status = res.status
    err.detalle = d
    throw err
  }
  return res.json()
}

async function descargarArchivo(path, nombreArchivo) {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const res = await fetchSeguro(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (res.status === 401 && token) {
    await cerrarSesionVencida()
    throw new Error(MSG_SESION_VENCIDA)
  }
  if (!res.ok) throw new Error(mensajePorEstado(res.status))

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nombreArchivo
  a.click()
  URL.revokeObjectURL(url)
}

// Quita los parámetros vacíos (desde/hasta/mes) antes de armar la query.
function limpiar(p) {
  return Object.fromEntries(Object.entries(p).filter(([, v]) => v !== undefined && v !== null && v !== ''))
}

export const api = {
  // Solo la administración (el servidor responde 404 a cualquier otra persona).
  panelNegocio: () => request('/metricas/panel'),
  // Avisos de actividad (solo administración; el servidor responde 404 a cualquier otra persona).
  actividadAvisos: (p = {}) => {
    const q = new URLSearchParams(limpiar(p)).toString()
    return request(`/avisos/actividad${q ? `?${q}` : ''}`, { sinCache: true })
  },
  preferenciasAvisos: () => request('/avisos/preferencias', { sinCache: true }),
  guardarPreferenciasAvisos: (data) => request('/avisos/preferencias', { method: 'PUT', body: data }),
  probarAvisos: () => request('/avisos/probar', { method: 'POST' }),
  // Buzón de opinión: cualquiera envía y ve lo suyo; lo demás es solo del administrador (404 al resto).
  enviarComentario: (data) => request('/comentarios', { method: 'POST', body: data }),
  misComentarios: () => request('/comentarios/mios', { sinCache: true }),
  // «Mi banco no aparece»: archivo de muestra en almacenamiento privado (5 MB, pdf/xls/xlsx/csv).
  almacenMuestras: () => request('/comentarios/almacen', { sinCache: true }),
  subirMuestraBanco: (comentarioId, archivo) => {
    const form = new FormData()
    form.append('archivo', archivo)
    return request(`/comentarios/${encodeURIComponent(comentarioId)}/adjunto`, { method: 'POST', body: form })
  },
  borrarMuestraBanco: (comentarioId) =>
    request(`/comentarios/${encodeURIComponent(comentarioId)}/adjunto`, { method: 'DELETE' }),
  descargarMuestraBanco: (comentarioId, nombre) =>
    descargarArchivo(`/comentarios/${encodeURIComponent(comentarioId)}/adjunto`, nombre || 'muestra'),
  comentariosAdmin: (p = {}) => {
    const q = new URLSearchParams(limpiar(p)).toString()
    return request(`/comentarios${q ? `?${q}` : ''}`, { sinCache: true })
  },
  cambiarComentario: (id, data) => request(`/comentarios/${encodeURIComponent(id)}`, { method: 'PATCH', body: data }),
  marcarComentariosVistos: (ids) => request('/comentarios/marcar-vistos', { method: 'POST', body: { ids } }),
  exportarComentariosCSV: () => descargarArchivo('/comentarios/exportar.csv', 'comentarios_cuadrame.csv'),
  cuentas: () => request('/cuentas'),
  crearCuenta: (data) => request('/cuentas', { method: 'POST', body: data }),
  editarCuenta: (id, data) => request(`/cuentas/${id}`, { method: 'PUT', body: data }),
  eliminarCuenta: (id) => request(`/cuentas/${id}`, { method: 'DELETE' }),
  resumenCuentas: () => request('/cuentas/resumen'),
  // Tasas manuales hacia la moneda base: GET {moneda_base, tasas:{MXN: 0.05}}; PUT {tasa}: 1 MONEDA = tasa de la base.
  tasasManuales: () => request('/perfil/tasas', { sinCache: true }),
  fijarTasaManual: (moneda, tasa) => request(`/perfil/tasas/${encodeURIComponent(moneda)}`, { method: 'PUT', body: { tasa } }),
  detalleCuenta: (id) => request(`/cuentas/${id}/detalle`),
  cuotasTarjeta: (cuentaId) => request(`/cuotas-tarjeta${cuentaId ? `?cuenta_id=${encodeURIComponent(cuentaId)}` : ''}`),
  crearCuotaTarjeta: (data) => request('/cuotas-tarjeta', { method: 'POST', body: data }),
  pagarCuotaTarjeta: (id) => request(`/cuotas-tarjeta/${id}/pagar-cuota`, { method: 'POST' }),
  eliminarCuotaTarjeta: (id) => request(`/cuotas-tarjeta/${id}`, { method: 'DELETE' }),
  ajustarSaldo: (id, saldoReal) => request(`/cuentas/${id}/ajustar-saldo`, { method: 'POST', body: { saldo_real: saldoReal } }),

  consentimientos: () => request('/consentimientos'),
  historialConsentimientos: () => request('/consentimientos/historial'),
  guardarConsentimientos: (version, items, origen = 'app') =>
    request('/consentimientos', { method: 'POST', body: { version, items, origen } }),

  // Filtros opcionales (los resuelve el servidor, así cubren TODO el historial y no solo lo cargado):
  // { porRevisar, q, categoria, tipo, cuentaId, desde, hasta } (fechas AAAA-MM-DD).
  movimientos: (limit = 100, offset = 0, { porRevisar = false, q, categoria, tipo, cuentaId, desde, hasta, origen } = {}) => {
    const extra = new URLSearchParams()
    if (origen) extra.set('origen', origen)
    if (q) extra.set('q', q)
    if (categoria) extra.set('categoria', categoria)
    if (tipo) extra.set('tipo', tipo)
    if (cuentaId) extra.set('cuenta_id', cuentaId)
    if (desde) extra.set('desde', desde)
    if (hasta) extra.set('hasta', `${hasta}T23:59:59`) // incluye todo el día "hasta"
    const resto = extra.toString()
    return request(
      `/movimientos?limit=${limit}&offset=${offset}${porRevisar ? '&por_revisar=true' : ''}${resto ? `&${resto}` : ''}`
    )
  },
  // Cuántos OTROS movimientos son del mismo comercio (misma huella): "Aplicar a los 12 anteriores".
  similaresConteo: (descripcion, excluirId) =>
    request(
      `/movimientos/similares/conteo?${new URLSearchParams({ descripcion, ...(excluirId ? { excluir_id: excluirId } : {}) })}`
    ),
  moverMovimientosMasivo: (movimientoIds, cuentaId) =>
    request('/movimientos/mover-masivo', {
      method: 'POST',
      body: { movimiento_ids: movimientoIds, cuenta_id: cuentaId },
    }),
  // motivo (opcional): 'duplicado' | 'error' | 'no_va'. Sin motivo el servidor usa 'duplicado'.
  eliminarMovimientosMasivo: (movimientoIds, motivo) =>
    request('/movimientos/eliminar-masivo', {
      method: 'POST',
      body: { movimiento_ids: movimientoIds, ...(motivo ? { motivo } : {}) },
    }),
  conteoPorRevisar: () => request('/movimientos/por-revisar/conteo'),
  // Bandeja "¿son tuyos?": movimientos que llegaron solos (Wallet, atajos) sin confirmar.
  movimientosPorConfirmar: () => request('/movimientos/por-confirmar'),
  // Pago de prueba del asistente de instalación: usa la API key, igual que el Atajo real,
  // para comprobar de punta a punta que la clave y la conexión funcionan.
  // Sin `apiKey` (la clave guardada ya no se puede leer: solo existe su hash) la prueba usa la
  // sesión del usuario en /rapido-prueba, que ejecuta exactamente el mismo registro.
  pagoDePrueba: (apiKey) =>
    request(apiKey ? '/movimientos/rapido' : '/movimientos/rapido-prueba', {
      method: 'POST',
      auth: !apiKey,
      headers: apiKey ? { 'X-Api-Key': apiKey } : undefined,
      body: { comercio: 'Pago de prueba CuadraMe', monto: '1.000', tarjeta: 'Prueba CuadraMe', moneda: 'COP', fuente: 'wallet' },
    }),
  // Prueba del "registro al cerrar la app": igual que el Atajo (sin comercio, fuente cierre_app).
  registroRapidoDePrueba: (apiKey) =>
    request(apiKey ? '/movimientos/rapido' : '/movimientos/rapido-prueba', {
      method: 'POST',
      auth: !apiKey,
      headers: apiKey ? { 'X-Api-Key': apiKey } : undefined,
      body: { tipo: 'gasto', monto: '1.000', descripcion: 'Prueba de registro rápido', fuente: 'cierre_app' },
    }),
  // Resumen semanal por correo (opt-in) y recordatorios de las tarjetas del Inicio
  resumenPreferencias: () => request('/resumen/preferencias'),
  guardarResumenPreferencias: (correo) => request('/resumen/preferencias', { method: 'PUT', body: { correo } }),
  // «Ocultar saldos»: se copia al servidor para que los avisos push semanales salgan sin montos.
  guardarOcultarMontos: (ocultar) => request('/resumen/preferencias', { method: 'PUT', body: { ocultar_montos: !!ocultar } }),
  recordatorios: () => request('/recordatorios'),
  // Consejos personalizados («Consejo para ti» en Inicio): reglas del servidor, sin IA externa
  consejos: () => request('/consejos'),
  // Tu plata trabajando: cajitas, rendimiento estimado y tasas de referencia
  rendimientos: () => request('/rendimientos'),
  crearCajita: (data) => request('/rendimientos/cajitas', { method: 'POST', body: data }),
  editarCajita: (id, data) => request(`/rendimientos/cajitas/${id}`, { method: 'PUT', body: data }),
  moverCajita: (id, data) => request(`/rendimientos/cajitas/${id}/mover`, { method: 'POST', body: data }),
  borrarCajita: (id) => request(`/rendimientos/cajitas/${id}`, { method: 'DELETE' }),
  tasasReferencia: () => request('/rendimientos/tasas'),
  tasasReferenciaAdmin: () => request('/rendimientos/tasas/admin'),
  guardarTasaReferencia: (id, data) => request(id ? `/rendimientos/tasas/${id}` : '/rendimientos/tasas', { method: id ? 'PUT' : 'POST', body: data }),
  // «Lo que te cuesta tu plata»: intereses, cuotas, comisiones y 4x1000 por mes y cuenta, alertas y suscripciones
  costosBancarios: (params = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
    return request(`/costos-bancarios${q ? `?${q}` : ''}`)
  },
  // Cómo le decimos a la persona: GET {nombre, sugerido, confirmado, email}; PUT {nombre} o {omitir: true}.
  nombrePerfil: () => request('/perfil/nombre', { sinCache: true }),
  guardarNombrePerfil: (data) => request('/perfil/nombre', { method: 'PUT', body: data }),
  // País, moneda e idioma: GET {pais, confirmado, moneda_base, config}; PUT {pais}.
  paisPerfil: () => request('/perfil/pais', { sinCache: true }),
  guardarPaisPerfil: (data) => request('/perfil/pais', { method: 'PUT', body: data }),
  recordatorioDiario: () => request('/perfil/recordatorio-diario'),
  actualizarRecordatorioDiario: (activo) =>
    request('/perfil/recordatorio-diario', { method: 'PUT', body: { activo } }),
  confirmarCategorias: (movimientoIds) =>
    request('/movimientos/confirmar-categorias', {
      method: 'POST',
      body: { movimiento_ids: movimientoIds ?? null },
    }),
  recategorizarComercio: (id, data) =>
    request(`/movimientos/${id}/recategorizar-comercio`, { method: 'POST', body: data }),
  movimiento: (id) => request(`/movimientos/${id}`),
  pasarAEfectivo: (id, crearCuenta = false) =>
    request(`/movimientos/${id}/pasar-a-efectivo?crear_cuenta=${crearCuenta ? 'true' : 'false'}`, { method: 'POST' }),
  editarMovimiento: (id, data) => request(`/movimientos/${id}`, { method: 'PUT', body: data }),
  crearTransferencia: (data) => request('/movimientos/transferencia', { method: 'POST', body: data }),
  crearMovimiento: (data) => request('/movimientos', { method: 'POST', body: data }),
  // motivo (opcional): 'duplicado' | 'error' | 'no_va' (ver docs/SALUD_DE_DATOS.md). Sin motivo = 'duplicado'.
  eliminarMovimiento: (id, motivo) => request(`/movimientos/${id}${motivo ? `?motivo=${motivo}` : ''}`, { method: 'DELETE' }),
  recategorizarMasivo: (movimientoIds, categoria, subcategoria) =>
    request('/movimientos/recategorizar-masivo', {
      method: 'POST',
      // subcategoria '' = quitarla (Deshacer de «solo agregué subcategoría»); sin valor = no tocarla
      body: subcategoria || subcategoria === '' ? { movimiento_ids: movimientoIds, categoria, subcategoria } : { movimiento_ids: movimientoIds, categoria },
    }),
  clasificar: (data) => request('/movimientos/clasificar', { method: 'POST', body: data }),

  presupuestos: () => request('/presupuestos'),
  crearPresupuesto: (data) => request('/presupuestos', { method: 'POST', body: data }),
  eliminarPresupuesto: (id) => request(`/presupuestos/${id}`, { method: 'DELETE' }),
  moverSobre: (origenId, destinoId, monto) =>
    request('/presupuestos/mover-sobre', {
      method: 'POST',
      body: { presupuesto_origen_id: origenId, presupuesto_destino_id: destinoId, monto },
    }),
  disponibleHoy: () => request('/presupuestos/disponible-hoy'),
  proyeccionPresupuestos: () => request('/planificacion/proyeccion'),
  configPlanificacion: () => request('/planificacion/config'),
  guardarConfigPlanificacion: (data) => request('/planificacion/config', { method: 'PUT', body: data }),
  distribuirIngreso: (monto) => request('/planificacion/distribuir-ingreso', { method: 'POST', body: { monto } }),
  planMeta: (data) => request('/planificacion/plan-meta', { method: 'POST', body: data }),
  descomposicionPatrimonio: () => request('/planificacion/patrimonio-descomposicion'),
  enMiBolsillo: () => request('/presupuestos/en-mi-bolsillo'),

  reporteMensual: (opts = {}) => {
    const mes = typeof opts === 'string' ? opts : opts.mes
    const { cuentaId, desde, hasta } = typeof opts === 'string' ? {} : opts
    const params = new URLSearchParams()
    if (mes) params.set('mes', mes)
    if (cuentaId) params.set('cuenta_id', cuentaId)
    if (desde) params.set('desde', desde)
    if (hasta) params.set('hasta', hasta)
    const qs = params.toString()
    return request(`/reportes/mensual${qs ? `?${qs}` : ''}`)
  },
  tendencias: (meses = 6) => request(`/reportes/tendencias?meses=${meses}`),

  plan: () => request('/pagos/plan'),
  crearCheckout: (successUrl, cancelUrl) =>
    request(
      `/pagos/checkout?success_url=${encodeURIComponent(successUrl)}&cancel_url=${encodeURIComponent(cancelUrl)}`,
      { method: 'POST' }
    ),

  metas: () => request('/metas'),
  crearMeta: (data) => request('/metas', { method: 'POST', body: data }),
  aportarMeta: (id, monto, cuentaId) =>
    request(`/metas/${id}/aportar?monto=${monto}${cuentaId ? `&cuenta_id=${cuentaId}` : ''}`, { method: 'POST' }),
  eliminarMeta: (id) => request(`/metas/${id}`, { method: 'DELETE' }),
  // Plan en palabras de cada meta (cuánto apartar, cuándo llegas, si vas adelantado) y de una meta que aún no existe.
  metasSugerencias: () => request('/metas/sugerencias', { sinCache: true }),
  simularMeta: (data) => request('/metas/simular', { method: 'POST', body: data }),

  recurrentes: () => request('/recurrentes'),
  sugerenciasRecurrentes: () => request('/recurrentes/sugerencias'),
  crearRecurrente: (data) => request('/recurrentes', { method: 'POST', body: data }),
  marcarRecurrentePagado: (id, crearMovimiento = true) =>
    request(`/recurrentes/${id}/marcar_pagado`, { method: 'POST', body: { crear_movimiento: crearMovimiento } }),
  eliminarRecurrente: (id) => request(`/recurrentes/${id}`, { method: 'DELETE' }),

  deudas: () => request('/deudas'),
  crearDeuda: (data) => request('/deudas', { method: 'POST', body: data }),
  pagarDeuda: (id, montoPagado, crearMovimiento = true) =>
    request(`/deudas/${id}/pagar`, { method: 'POST', body: { monto_pagado: montoPagado, crear_movimiento: crearMovimiento } }),
  eliminarDeuda: (id) => request(`/deudas/${id}`, { method: 'DELETE' }),
  estrategiaDeudas: (extra = 0) => request(`/deudas/estrategia?extra=${encodeURIComponent(extra)}`),

  patrimonio: () => request('/patrimonio'),
  crearActivo: (data) => request('/patrimonio/activos', { method: 'POST', body: data }),
  editarActivo: (id, data) => request(`/patrimonio/activos/${id}`, { method: 'PUT', body: data }),
  eliminarActivo: (id) => request(`/patrimonio/activos/${id}`, { method: 'DELETE' }),
  registrarValorActivo: (id, valor, fecha) =>
    request(`/patrimonio/activos/${id}/valor`, { method: 'POST', body: { valor, fecha } }),
  registrarFlujoActivo: (id, monto, fecha, nota = '') =>
    request(`/patrimonio/activos/${id}/flujos`, { method: 'POST', body: { monto, fecha, nota } }),

  inversiones: () => request('/inversiones'),
  opcionesInversiones: () => request('/inversiones/opciones'),
  guardarOpcionesInversiones: (data) => request('/inversiones/opciones', { method: 'PUT', body: data }),
  tickersInversion: (q) => request(`/inversiones/tickers?q=${encodeURIComponent(q)}`),
  crearBrokerInversion: (data) => request('/inversiones/brokers', { method: 'POST', body: data }),
  crearPosicionInversion: (data) => request('/inversiones/posiciones', { method: 'POST', body: data }),
  posicionInversion: (id) => request(`/inversiones/posiciones/${id}`),
  eliminarPosicionInversion: (id) => request(`/inversiones/posiciones/${id}`, { method: 'DELETE' }),
  precioManualInversion: (id, precio) =>
    request(`/inversiones/posiciones/${id}/precio-manual`, { method: 'POST', body: { precio } }),
  registrarTransaccionInversion: (id, data) =>
    request(`/inversiones/posiciones/${id}/transacciones`, { method: 'POST', body: data }),
  eliminarTransaccionInversion: (txId) => request(`/inversiones/transacciones/${txId}`, { method: 'DELETE' }),
  actualizarPreciosInversiones: () => request('/inversiones/precios/actualizar', { method: 'POST' }),
  importarInversiones: (data) => request('/inversiones/importar', { method: 'POST', body: data }),

  aplicarExtractoTarjeta: (cuentaId, datos) =>
    request(`/tarjetas/${cuentaId}/aplicar-extracto`, { method: 'POST', body: datos }),
  procesarExtracto: (pdfBase64, cuentaId, password = '') =>
    request('/conciliacion/procesar', {
      method: 'POST',
      body: { pdf_base64: pdfBase64, cuenta_id: cuentaId, password },
    }),
  historialExtractos: () => request('/conciliacion/historial'),
  // Cambiar la cuenta de un extracto: la vista previa no cambia nada; el cambio pide confirmar.
  previaCambiarCuentaExtracto: (id, cuentaId) =>
    request(`/conciliacion/historial/${id}/cambiar-cuenta/previa?cuenta_id=${encodeURIComponent(cuentaId)}`),
  cambiarCuentaExtracto: (id, cuentaId) =>
    request(`/conciliacion/historial/${id}/cambiar-cuenta`, { method: 'POST', body: { cuenta_id: cuentaId, confirmar: true } }),
  // «Arreglar mis extractos de la tarjeta»: la previa no cambia nada ni toca Gmail; arreglar pide confirmar.
  // Se arregla de a uno (`maximo: 1`) para mostrar el avance; `excluir` = los que esta tanda ya intentó.
  previaArreglarTarjetas: () => request('/conciliacion/tarjetas/arreglar/previa'),
  arreglarTarjetas: ({ maximo = 12, excluir = [], continuar = false } = {}) =>
    request('/conciliacion/tarjetas/arreglar', { method: 'POST', body: { confirmar: true, maximo, excluir, continuar } }),
  // «Completar mis extractos: rendimientos e impuestos»: la previa no cambia nada ni toca Gmail; registrar pide confirmar.
  previaRendimientos: () => request('/conciliacion/ajustes-extracto/previa'),
  registrarRendimientos: ({ maximo = 12, excluir = [], continuar = false } = {}) =>
    request('/conciliacion/ajustes-extracto/registrar', { method: 'POST', body: { confirmar: true, maximo, excluir, continuar } }),
  obtenerReviewExtracto: (id) => request(`/conciliacion/historial/${id}`),
  resolverDudosos: (id, mismos, distintos) =>
    request(`/conciliacion/historial/${id}/resolver-dudosos`, { method: 'POST', body: { mismos, distintos } }),
  // `aprender` (opcional): { recordar: [fingerprint], aplicar_anteriores: [fingerprint] }
  importarFaltantes: (id, fingerprints, categorias, aprender) =>
    request(`/conciliacion/historial/${id}/importar`, {
      method: 'POST',
      body: aprender ? { fingerprints, categorias, ...aprender } : { fingerprints, categorias },
    }),
  // Cuadre con el extracto (saldo del banco frente al de tus movimientos).
  cuadreCuenta: (cuentaId) => request(`/conciliacion/cuadre?cuenta_id=${encodeURIComponent(cuentaId)}`),
  cuadreEncadenado: (cuentaId) => request(`/conciliacion/cuadre/encadenado?cuenta_id=${encodeURIComponent(cuentaId)}`, { sinCache: true }),
  cuadreResumen: () => request('/conciliacion/cuadre/resumen'),
  cuadreEvaluar: (body) => request('/conciliacion/cuadre/evaluar', { method: 'POST', body }),
  cuadreQueFalta: (cuentaId, historialId) =>
    request(`/conciliacion/cuadre/que-falta?cuenta_id=${encodeURIComponent(cuentaId)}${historialId ? `&historial_id=${encodeURIComponent(historialId)}` : ''}`),
  cuadreReleerSaldos: () => request('/conciliacion/cuadre/releer-saldos', { method: 'POST' }),
  cuadreSaldos: (body) => request('/conciliacion/cuadre/saldos', { method: 'POST', body }),
  cuadreAjuste: (body) => request('/conciliacion/cuadre/ajuste', { method: 'POST', body }),
  cuadreSaldoInicial: (body) => request('/conciliacion/cuadre/saldo-inicial', { method: 'POST', body }),
  cuadreSaldoInicialAuto: () => request('/conciliacion/cuadre/saldo-inicial-auto', { method: 'POST' }),
  cuadreSaldoInicialAutoEstado: (cuentaId) =>
    request(`/conciliacion/cuadre/saldo-inicial-auto/${encodeURIComponent(cuentaId)}`, { sinCache: true }),
  cuadreSaldoInicialAutoRecalcular: (cuentaId) =>
    request('/conciliacion/cuadre/saldo-inicial-auto/recalcular', { method: 'POST', body: { cuenta_id: cuentaId } }),
  cuadreDeshacer: (movimientoId) =>
    request('/conciliacion/cuadre/deshacer', { method: 'POST', body: { movimiento_id: movimientoId, confirmar: true } }),
  eliminarHistorialExtracto: (id) => request(`/conciliacion/historial/${id}`, { method: 'DELETE' }),

  categorias: (incluirInactivas = false) =>
    request(`/categorias${incluirInactivas ? '?incluir_inactivas=true' : ''}`),
  crearCategoria: (data) => request('/categorias', { method: 'POST', body: data }),
  editarCategoria: (id, data) => request(`/categorias/${id}`, { method: 'PUT', body: data }),
  eliminarCategoria: (id, moverA) =>
    request(`/categorias/${id}${moverA ? '?mover_a=' + encodeURIComponent(moverA) : ''}`, { method: 'DELETE' }),
  // Subcategorías: un nivel de detalle opcional dentro de cada categoría (docs/SUBCATEGORIAS.md).
  subcategorias: () => request('/subcategorias'),
  crearSubcategoria: (categoria, nombre) => request('/subcategorias', { method: 'POST', body: { categoria, nombre } }),
  editarSubcategoria: (id, nombre) => request(`/subcategorias/${id}`, { method: 'PUT', body: { nombre } }),
  eliminarSubcategoria: (id) => request(`/subcategorias/${id}`, { method: 'DELETE' }),
  // Desglose de UNA categoría por subcategoría en el periodo del informe (incluye «Sin subcategoría»).
  desgloseSubcategorias: (categoria, { periodo = 'este_mes', desde, hasta, mes } = {}) => {
    const q = new URLSearchParams({ categoria, periodo })
    if (desde) q.set('desde', desde)
    if (hasta) q.set('hasta', hasta)
    if (mes) q.set('mes', mes)
    return request(`/informes/gasto/subcategorias?${q.toString()}`)
  },
  reordenarCategorias: (ids) => request('/categorias/orden', { method: 'PUT', body: { ids } }),

  // Derecho de supresión: el backend exige la palabra escrita por la persona.
  eliminarMiCuenta: (confirmacion = 'ELIMINAR') =>
    request('/perfil/eliminar-cuenta', { method: 'POST', body: { confirmacion } }),
  // Derecho de acceso: ZIP con todo lo que CuadraMe guarda de la persona (JSON + un CSV por tabla).
  descargarMisDatos: () => descargarArchivo('/perfil/mis-datos', 'cuadrame_mis_datos.zip'),
  // Importar mi respaldo (el ZIP de arriba): vista previa sin escribir, importar y deshacer la última.
  vistaPreviaRespaldo: (archivo) => {
    const f = new FormData()
    f.append('archivo', archivo)
    return request('/perfil/importar-respaldo/vista-previa', { method: 'POST', body: f })
  },
  importarRespaldo: (archivo) => {
    const f = new FormData()
    f.append('archivo', archivo)
    f.append('confirmar', 'true')
    return request('/perfil/importar-respaldo', { method: 'POST', body: f })
  },
  ultimaImportacionRespaldo: () => request('/perfil/importar-respaldo/ultima', { sinCache: true }),
  deshacerImportacionRespaldo: () => request('/perfil/importar-respaldo/deshacer', { method: 'POST' }),
  apiKey: () => request('/perfil/api-key'),
  regenerarApiKey: () => request('/perfil/api-key/regenerar', { method: 'POST' }),
  confianzaAutoimport: () => request('/perfil/confianza-autoimport'),
  actualizarConfianzaAutoimport: (valor) =>
    request('/perfil/confianza-autoimport', { method: 'PUT', body: { confianza_autoimport: valor } }),

  gmailEstado: () => request('/correos/gmail/estado'),
  gmailConectar: () => request('/correos/gmail/conectar', { sinCache: true }), // URL de OAuth con estado único
  gmailDesconectar: () => request('/correos/gmail/desconectar', { method: 'POST' }),
  gmailEtiqueta: (etiqueta) => request(`/correos/gmail/etiqueta?etiqueta=${encodeURIComponent(etiqueta)}`, { method: 'POST' }),
  // params: { completa: true } fuerza la ventana larga (90 días); cada llamada procesa un lote.
  // params.tipo: 'movimientos' | 'extractos' | 'todo' (por defecto): cada uno es un uso independiente del correo.
  sincronizarCorreos: (params) => {
    const q = []
    if (params?.completa) q.push('completa=true')
    if (params?.dias) q.push(`dias=${params.dias}`)
    if (params?.releer) q.push('releer=true')
    if (params?.tipo && params.tipo !== 'todo') q.push(`tipo=${params.tipo}`)
    return request(`/correos/sincronizar${q.length ? `?${q.join('&')}` : ''}`, { method: 'POST' })
  },
  // Enciende/apaga cada uso del correo: { leer_movimientos?: bool, leer_extractos?: bool }.
  gmailLectura: (data) => request('/correos/gmail/lectura', { method: 'PUT', body: data }),
  correosLista: (filtro = 'nuevos', offset = 0, limite = 30) =>
    request(`/correos/lista?filtro=${filtro}&limite=${limite}&offset=${offset}`),
  conexionesEstado: () => request('/conexiones/estado'),
  // Pantalla Sincronización: grilla cuentas x meses, tareas y cola de categorías por preguntar.
  // `hasta` ('YYYY-MM') desplaza la ventana de meses; el backend actual la ignora (siempre los últimos 6).
  sincronizacionEstado: (hasta) => request(`/sincronizacion/estado${hasta ? `?hasta=${hasta}` : ''}`),
  sincronizacionPorCategorizar: (offset = 0, limite = 10) =>
    request(`/sincronizacion/por-categorizar?limite=${limite}&offset=${offset}`),
  correosPendientes: () => request('/correos/pendientes'),
  editarCorreo: (id, data) => request(`/correos/${id}`, { method: 'PATCH', body: data }),
  aprobarCorreo: (id, cuentaId, extra = {}) => request(`/correos/${id}/aprobar`, { method: 'POST', body: { cuenta_id: cuentaId, ...extra } }),
  descartarCorreo: (id) => request(`/correos/${id}/descartar`, { method: 'POST' }),
  // «Mostrar de todos modos / No es duplicado»: un correo que se dio por ya registrado era otro gasto igual.
  correoNoEsDuplicado: (id) => request(`/correos/${id}/no-es-duplicado`, { method: 'POST' }),
  // Recuperar un correo descartado (o ignorado con monto): vuelve a «Por revisar».
  recuperarCorreo: (id) => request(`/correos/${id}/recuperar`, { method: 'POST' }),
  correosDescartados: (limite = 50) => request(`/correos/lista?filtro=descartados&limite=${limite}&offset=0`),
  correosYaRegistrados: (limite = 50) => request(`/correos/lista?filtro=ya_registrados&limite=${limite}&offset=0`),
  // Buscar duplicados: sugiere grupos de movimientos repetidos; unir conserva uno; nada se borra solo.
  buscarDuplicados: () => request('/duplicados/buscar', { sinCache: true }),
  unirDuplicados: (conservarId, unirIds) =>
    request('/duplicados/unir', { method: 'POST', body: { conservar_id: conservarId, unir_ids: unirIds } }),
  noEsDuplicado: (movimientoIds) =>
    request('/duplicados/no-es-duplicado', { method: 'POST', body: { movimiento_ids: movimientoIds } }),
  extractosCorreo: (estado, offset = 0, limite = 50) =>
    request(`/correos/extractos?limite=${limite}&offset=${offset}${estado ? `&estado=${estado}` : ''}`),
  conciliarExtractoCorreo: (id, cuentaId) =>
    request(`/correos/extractos/${id}/conciliar`, { method: 'POST', body: { cuenta_id: cuentaId } }),
  // «¿No ves un extracto?»: busca por asunto en tu Gmail (solo lectura) y luego procesa los elegidos.
  // modo 'movimiento': sin exigir PDF adjunto (una notificación del banco); por defecto 'extracto'.
  buscarExtractosPorAsunto: (asunto, modo = 'extracto') => request('/correos/extractos/buscar-asunto', { method: 'POST', body: { asunto, modo } }),
  procesarExtractosPorAsunto: (ids, modo = 'extracto') => request('/correos/extractos/buscar-asunto/procesar', { method: 'POST', body: { ids, modo } }),
  // «Enséñale a leer este correo»: reglas PERSONALES de lectura. `vista` baja el texto del correo (solo para esta persona).
  reglasCorreo: () => request('/reglas-correo', { sinCache: true }),
  vistaReglaCorreo: (datos) => request('/reglas-correo/vista', { method: 'POST', body: datos }),
  crearReglaCorreo: (datos) => request('/reglas-correo', { method: 'POST', body: datos }),
  aplicarReglaCorreoAnteriores: (id) => request(`/reglas-correo/${id}/aplicar-anteriores`, { method: 'POST' }),
  borrarReglaCorreo: (id) => request(`/reglas-correo/${id}`, { method: 'DELETE' }),
  descartarExtractoCorreo: (id) => request(`/correos/extractos/${id}/descartar`, { method: 'POST' }),
  // «Intentar de nuevo»: vuelve a bajar y abrir el PDF (no importa movimientos).
  reintentarExtractoCorreo: (id) => request(`/correos/extractos/${id}/reintentar`, { method: 'POST' }),
  // Extractos en error: reintentar el de un correo («Reintentar»), quitarlo de la lista y reintentar los de clave en lote.
  reintentarHistorialError: (id) => request(`/conciliacion/historial/${id}/reintentar`, { method: 'POST' }),
  quitarHistorialError: (id) => request(`/conciliacion/historial/${id}/error`, { method: 'DELETE' }),
  releerExtracto: (historialId) => request(`/conciliacion/historial/${historialId}/releer`, { method: 'POST' }),
  releerPendientes: () => request('/conciliacion/releer-pendientes', { method: 'POST' }),
  // Autoarreglo (docs/AUTOARREGLO.md): la app ordena sola las cuentas. `correr` hace un tramo y dice si queda más
  // ('trabajando'); `lotes` es lo que hizo; `deshacer` revierte un lote completo.
  correrAutoarreglo: () => request('/autoarreglo/correr', { method: 'POST', sinCache: true }),
  lotesAutoarreglo: () => request('/autoarreglo/lotes', { sinCache: true }),
  deshacerLoteAutoarreglo: (lote) => request(`/autoarreglo/lotes/${encodeURIComponent(lote)}/deshacer`, { method: 'POST' }),
  // Salud de datos (ver docs/SALUD_DE_DATOS.md): hallazgos de la persona y «Crear tu cuenta de tarjeta».
  salud: () => request('/salud'),
  saludCrearTarjeta: (banco) => request('/salud/crear-tarjeta', { method: 'POST', body: { banco } }),
  reintentarErroresExtractos: () => request('/conciliacion/reintentar-errores', { method: 'POST' }),
  // «Todos los extractos»: la lista completa (también viene en /sincronizacion/estado como `todos_extractos`).
  todosLosExtractos: () => request('/sincronizacion/extractos', { sinCache: true }),
  // Fijar de qué mes es un extracto cuando no se pudo deducir. `mes` = 'AAAA-MM'.
  fijarMesExtracto: (id, mes) => request(`/sincronizacion/extractos/${id}/mes`, { method: 'PUT', body: { mes } }),
  clavePdfEstado: () => request('/correos/clave-pdf'),
  guardarClavePdf: (clave) => request('/correos/clave-pdf', { method: 'PUT', body: { clave } }),
  borrarClavePdf: () => request('/correos/clave-pdf', { method: 'DELETE' }),
  // Prueba la clave guardada ahora: en un extracto (extractoId) o en todos los que piden clave.
  probarClavePdf: (extractoId) =>
    request('/correos/clave-pdf/probar', { method: 'POST', body: extractoId ? { extracto_id: extractoId } : {} }),
  // Punto de partida («empezar desde hoy» / «recrear mi histórico»).
  puntoDePartida: () => request('/perfil/punto-de-partida'),
  guardarPuntoDePartida: (datos) => request('/perfil/punto-de-partida', { method: 'PUT', body: datos }),
  coberturaPuntoDePartida: () => request('/perfil/punto-de-partida/cobertura'),
  conciliacionPuntoDePartida: () => request('/perfil/punto-de-partida/conciliacion'),
  ajustarSaldosPuntoDePartida: (cuentaIds = []) =>
    request('/perfil/punto-de-partida/ajustar-saldos', { method: 'POST', body: { cuenta_ids: cuentaIds } }),

  resumenSemanal: (desde, hasta) =>
    request(`/insights/resumen-semanal${desde && hasta ? `?desde=${desde}&hasta=${hasta}` : ''}`),
  // Informe "en qué gasto": p = { periodo, desde, hasta, mes }
  ingresosGastos: (p = {}) => request(`/reportes/ingresos-gastos?${new URLSearchParams(limpiar(p)).toString()}`),
  evolucion: (p = {}) => request(`/reportes/evolucion?${new URLSearchParams(limpiar(p)).toString()}`),
  informeNoSeCuenta: (p = {}) => request(`/informes/no-se-cuenta?${new URLSearchParams(limpiar(p)).toString()}`),
  sugerenciasTraslado: () => request('/traslados/sugerencias'),
  decidirTraslado: (cuerpo) => request('/traslados/decidir', { method: 'POST', body: cuerpo }),
  informeGasto: (p = {}) => request(`/informes/gasto?${new URLSearchParams(limpiar(p)).toString()}`),
  informeMovimientos: (p = {}) => request(`/informes/gasto/movimientos?${new URLSearchParams(limpiar(p)).toString()}`),
  evolucionCategorias: (p = {}) => request(`/informes/evolucion-categorias?${new URLSearchParams(limpiar(p)).toString()}`),
  informeMeses: () => request('/informes/meses'),
  gastoDiario: (desde, hasta) =>
    request(`/informes/diario${desde && hasta ? `?desde=${desde}&hasta=${hasta}` : ''}`),
  edadDelDinero: () => request('/insights/edad-del-dinero'),
  saludFinanciera: () => request('/insights/salud-financiera'),
  wrapped: (mes) => request(`/reportes/wrapped${mes ? `?mes=${mes}` : ''}`),
  alertasProactivas: () => request('/insights/alertas-proactivas'),
  asistenteSugerencias: () => request('/asistente/sugerencias'),
  asistenteMensaje: (texto) => request('/asistente/mensaje', { method: 'POST', body: { texto } }),
  asistenteConfirmarMovimiento: (data) => request('/asistente/confirmar/movimiento', { method: 'POST', body: data }),
  asistenteConfirmarPlan: (data) => request('/asistente/confirmar/plan', { method: 'POST', body: data }),
  preguntar: (pregunta) => request('/insights/preguntar', { method: 'POST', body: { pregunta } }),

  pushPublicKey: () => request('/push/vapid-public-key', { auth: false }),
  pushSuscribir: (data) => request('/push/suscribir', { method: 'POST', body: data }),
  pushDesuscribir: (endpoint) => request(`/push/desuscribir?endpoint=${encodeURIComponent(endpoint)}`, { method: 'POST' }),
  pushProbar: () => request('/push/probar', { method: 'POST' }),

  buscarMovimientos: (filtros) => request(`/movimientos?${new URLSearchParams(filtros).toString()}`),

  exportarCSV: () => descargarArchivo('/exportar/movimientos.csv', 'movimientos_cuadrame.csv'),
  exportarExcel: () => descargarArchivo('/exportar/movimientos.xlsx', 'movimientos_cuadrame.xlsx'),

  invitarACuenta: (cuentaId, email, rol = 'viewer') =>
    request(`/cuentas/${cuentaId}/invitar`, { method: 'POST', body: { email, rol } }),
  invitacionesDeCuenta: (cuentaId) => request(`/cuentas/${cuentaId}/invitaciones`),
  compartidaCon: (cuentaId) => request(`/cuentas/${cuentaId}/compartida-con`),
  misInvitacionesPendientes: () => request('/cuentas/invitaciones/pendientes'),
  aceptarInvitacion: (id) => request(`/cuentas/invitaciones/${id}/aceptar`, { method: 'POST' }),
  rechazarInvitacion: (id) => request(`/cuentas/invitaciones/${id}/rechazar`, { method: 'POST' }),
  revocarAcceso: (cuentaId, usuarioId) => request(`/cuentas/${cuentaId}/compartir/${usuarioId}`, { method: 'DELETE' }),

  reglasCategoria: () => request('/reglas-categoria'),
  crearReglaCategoria: (data) => request('/reglas-categoria', { method: 'POST', body: data }),
  eliminarReglaCategoria: (id) => request(`/reglas-categoria/${id}`, { method: 'DELETE' }),
  // Aprendizaje: guarda la regla del comercio de una descripción (una por huella) y, si se pide, recategoriza los anteriores.
  aprenderRegla: (data) => request('/reglas-categoria/aprender', { method: 'POST', body: data }),
  vocabularioCategorias: () => request('/categorias/vocabulario'),
  // Reglas a elección: vista previa, sugerencias (el usuario elige cuáles crear) y acciones en lote.
  vistaPreviaRegla: (descripcion, excluirId) =>
    request(`/reglas-categoria/vista-previa?descripcion=${encodeURIComponent(descripcion)}${excluirId ? `&excluir_id=${excluirId}` : ''}`),
  sugerenciasReglas: () => request('/reglas-categoria/sugerencias'),
  crearSugerencias: (elegidas, aplicarAnteriores = false) =>
    request('/reglas-categoria/sugerencias/crear', { method: 'POST', body: { elegidas, aplicar_anteriores: aplicarAnteriores } }),
  descartarSugerencias: (huellas) => request('/reglas-categoria/sugerencias/descartar', { method: 'POST', body: { huellas } }),
  restaurarSugerencias: (huellas) => request('/reglas-categoria/sugerencias/restaurar', { method: 'POST', body: { huellas } }),
  reglasEnLote: (ids, accion) => request('/reglas-categoria/lote', { method: 'POST', body: { ids, accion } }),
  // «Por categorizar» a elección (lista por comercio, acciones sobre lo seleccionado, deshacer).
  porCategorizar: (limite = 10, todos = false) => request(`/por-categorizar?limite=${limite}${todos ? '&todos=true' : ''}`),
  accionPorCategorizar: (body) => request('/por-categorizar/accion', { method: 'POST', body }),
  deshacerPorCategorizar: (body) => request('/por-categorizar/deshacer', { method: 'POST', body }),
  silenciosPorCategorizar: () => request('/por-categorizar/silencios'),
  quitarSilencios: (huellas) => request('/por-categorizar/silencios/quitar', { method: 'POST', body: { huellas } }),
  explicarCategoria: (q) => request(`/categorias/explicar?q=${encodeURIComponent(q)}`),

  flujoCajaFuturo: (meses = 3) => request(`/reportes/flujo-caja-futuro?meses=${meses}`),

  vidasAhorcado: () => request('/ahorcado/vidas'),
  nuevaPartidaAhorcado: () => request('/ahorcado/nueva-partida', { method: 'POST' }),
  adivinarLetraAhorcado: (partidaId, letra) =>
    request(`/ahorcado/${partidaId}/adivinar`, { method: 'POST', body: { letra } }),

  // Gastos compartidos (cuentas con amigos)
  contactosGasto: () => request('/gastos-compartidos/contactos'),
  crearContactoGasto: (data) => request('/gastos-compartidos/contactos', { method: 'POST', body: data }),
  eliminarContactoGasto: (id) => request(`/gastos-compartidos/contactos/${id}`, { method: 'DELETE' }),
  gruposGasto: () => request('/gastos-compartidos/grupos'),
  crearGrupoGasto: (data) => request('/gastos-compartidos/grupos', { method: 'POST', body: data }),
  eliminarGrupoGasto: (id) => request(`/gastos-compartidos/grupos/${id}`, { method: 'DELETE' }),
  calcularDivision: (data) => request('/gastos-compartidos/calcular', { method: 'POST', body: data }),
  crearGastoCompartido: (data) => request('/gastos-compartidos', { method: 'POST', body: data }),
  gastosCompartidos: (grupoId) => request(`/gastos-compartidos${grupoId ? `?grupo_id=${grupoId}` : ''}`),
  eliminarGastoCompartido: (id) => request(`/gastos-compartidos/${id}`, { method: 'DELETE' }),
  saldosGasto: (grupoId) => request(`/gastos-compartidos/saldos${grupoId ? `?grupo_id=${grupoId}` : ''}`),
  registrarPagoGasto: (data) => request('/gastos-compartidos/liquidaciones', { method: 'POST', body: data }),

  // Foto de factura (la IA solo sugiere; nada se guarda hasta que el usuario confirme)
  escanearFactura: (imagenBase64, mime) =>
    request('/facturas/escanear', { method: 'POST', body: { imagen_base64: imagenBase64, mime } }),

  // Importar CSV / Excel: la vista previa NO guarda nada; solo /confirmar crea movimientos
  importarVistaPrevia: (data) => request('/importar/vista-previa', { method: 'POST', body: data }),
  importarConfirmar: (data) => request('/importar/confirmar', { method: 'POST', body: data }),

  // Impuestos Colombia (informativo)
  impuestosResumen: (anio) => request(`/impuestos/resumen${anio ? `?anio=${anio}` : ''}`),
  impuestosAjustes: (cuentaExentaId) =>
    request('/impuestos/ajustes', { method: 'PUT', body: { cuenta_exenta_gmf_id: cuentaExentaId || null } }),
  impuestosMarcar: (movimientoId, data) =>
    request(`/impuestos/marcas/${movimientoId}`, { method: 'PUT', body: data }),
  impuestosQuitarMarca: (movimientoId) => request(`/impuestos/marcas/${movimientoId}`, { method: 'DELETE' }),
  rentaEstimada: (anio) => request(`/impuestos/renta-estimada${anio ? `?anio=${anio}` : ''}`),
  gmfEstimado: (mes) => request(`/impuestos/gmf-estimado${mes ? `?mes=${mes}` : ''}`),
  rentaResumenCsv: (anio) => descargarArchivo(`/impuestos/renta-resumen.csv?anio=${anio}`, `cuadrame_resumen_renta_${anio}.csv`),
  impuestosExcel: (anio) => descargarArchivo(`/impuestos/exportar.xlsx?anio=${anio}`, `cuadrame_renta_${anio}.xlsx`),

  // Cierre de mes
  cierresMes: () => request('/cierre-mes'),
  // El cierre del mes contra los extractos, por banco y cuenta (sin `mes`: el mes anterior).
  cierreExtractos: (mes) => request(`/cierre-mes/extractos${mes ? `?mes=${encodeURIComponent(mes)}` : ''}`, { sinCache: true }),
  // 404 = aún no hay cierre de ese mes (estado normal): se devuelve null en vez de lanzar.
  cierreMes: (mes) =>
    request(`/cierre-mes/${mes}`).catch((e) => {
      if (e?.status === 404) return null
      throw e
    }),
  generarCierreMes: (mes) => request(`/cierre-mes/${mes}/generar`, { method: 'POST' }),
  cierrePreferencias: () => request('/cierre-mes/preferencias'),
  guardarCierrePreferencias: (correo) => request('/cierre-mes/preferencias', { method: 'PUT', body: { correo } }),
}

