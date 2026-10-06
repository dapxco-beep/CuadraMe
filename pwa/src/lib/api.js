import { supabase } from './supabase'
import { borrarSeguridad } from './seguridad'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const MSG_SIN_CONEXION = 'Sin conexión. Revisa tu internet e intenta de nuevo.'
export const MSG_ERROR_SERVIDOR = 'Tuvimos un problema. Intenta de nuevo en un momento.'
export const MSG_SESION_VENCIDA = 'Tu sesión venció. Vuelve a iniciar sesión para continuar.'

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

async function request(path, { method = 'GET', body, auth = true, headers: extra } = {}) {
  const headers = { 'Content-Type': 'application/json', ...(extra || {}) }
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
    body: body ? JSON.stringify(body) : undefined,
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
    const err = new Error(mensaje || `Error ${res.status}`)
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
  if (!res.ok) throw new Error(res.status >= 500 ? MSG_ERROR_SERVIDOR : `Error ${res.status}`)

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
  cuentas: () => request('/cuentas'),
  crearCuenta: (data) => request('/cuentas', { method: 'POST', body: data }),
  editarCuenta: (id, data) => request(`/cuentas/${id}`, { method: 'PUT', body: data }),
  eliminarCuenta: (id) => request(`/cuentas/${id}`, { method: 'DELETE' }),
  resumenCuentas: () => request('/cuentas/resumen'),
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
  movimientos: (limit = 100, offset = 0, { porRevisar = false, q, categoria, tipo, cuentaId, desde, hasta } = {}) => {
    const extra = new URLSearchParams()
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
  eliminarMovimientosMasivo: (movimientoIds) =>
    request('/movimientos/eliminar-masivo', { method: 'POST', body: { movimiento_ids: movimientoIds } }),
  conteoPorRevisar: () => request('/movimientos/por-revisar/conteo'),
  // Bandeja "¿son tuyos?": movimientos que llegaron solos (Wallet, atajos) sin confirmar.
  movimientosPorConfirmar: () => request('/movimientos/por-confirmar'),
  // Pago de prueba del asistente de instalación: usa la API key, igual que el Atajo real,
  // para comprobar de punta a punta que la clave y la conexión funcionan.
  pagoDePrueba: (apiKey) =>
    request('/movimientos/rapido', {
      method: 'POST',
      auth: false,
      headers: { 'X-Api-Key': apiKey },
      body: { comercio: 'Pago de prueba CuadraMe', monto: '1.000', tarjeta: 'Prueba CuadraMe', moneda: 'COP', fuente: 'wallet' },
    }),
  // Prueba del "registro al cerrar la app": igual que el Atajo (sin comercio, fuente cierre_app).
  registroRapidoDePrueba: (apiKey) =>
    request('/movimientos/rapido', {
      method: 'POST',
      auth: false,
      headers: { 'X-Api-Key': apiKey },
      body: { tipo: 'gasto', monto: '1.000', descripcion: 'Prueba de registro rápido', fuente: 'cierre_app' },
    }),
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
  editarMovimiento: (id, data) => request(`/movimientos/${id}`, { method: 'PUT', body: data }),
  crearTransferencia: (data) => request('/movimientos/transferencia', { method: 'POST', body: data }),
  crearMovimiento: (data) => request('/movimientos', { method: 'POST', body: data }),
  eliminarMovimiento: (id) => request(`/movimientos/${id}`, { method: 'DELETE' }),
  recategorizarMasivo: (movimientoIds, categoria) =>
    request('/movimientos/recategorizar-masivo', {
      method: 'POST',
      body: { movimiento_ids: movimientoIds, categoria },
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

  aplicarExtractoTarjeta: (cuentaId, datos) =>
    request(`/tarjetas/${cuentaId}/aplicar-extracto`, { method: 'POST', body: datos }),
  procesarExtracto: (pdfBase64, cuentaId, password = '') =>
    request('/conciliacion/procesar', {
      method: 'POST',
      body: { pdf_base64: pdfBase64, cuenta_id: cuentaId, password },
    }),
  historialExtractos: () => request('/conciliacion/historial'),
  obtenerReviewExtracto: (id) => request(`/conciliacion/historial/${id}`),
  // `aprender` (opcional): { recordar: [fingerprint], aplicar_anteriores: [fingerprint] }
  importarFaltantes: (id, fingerprints, categorias, aprender) =>
    request(`/conciliacion/historial/${id}/importar`, {
      method: 'POST',
      body: aprender ? { fingerprints, categorias, ...aprender } : { fingerprints, categorias },
    }),
  eliminarHistorialExtracto: (id) => request(`/conciliacion/historial/${id}`, { method: 'DELETE' }),

  categorias: (incluirInactivas = false) =>
    request(`/categorias${incluirInactivas ? '?incluir_inactivas=true' : ''}`),
  crearCategoria: (data) => request('/categorias', { method: 'POST', body: data }),
  editarCategoria: (id, data) => request(`/categorias/${id}`, { method: 'PUT', body: data }),
  eliminarCategoria: (id, moverA) =>
    request(`/categorias/${id}${moverA ? '?mover_a=' + encodeURIComponent(moverA) : ''}`, { method: 'DELETE' }),
  reordenarCategorias: (ids) => request('/categorias/orden', { method: 'PUT', body: { ids } }),

  eliminarMiCuenta: () => request('/perfil/eliminar-cuenta', { method: 'POST', body: { confirmacion: 'ELIMINAR' } }),
  apiKey: () => request('/perfil/api-key'),
  regenerarApiKey: () => request('/perfil/api-key/regenerar', { method: 'POST' }),
  confianzaAutoimport: () => request('/perfil/confianza-autoimport'),
  actualizarConfianzaAutoimport: (valor) =>
    request('/perfil/confianza-autoimport', { method: 'PUT', body: { confianza_autoimport: valor } }),

  gmailEstado: () => request('/correos/gmail/estado'),
  gmailConectar: () => request('/correos/gmail/conectar'),
  gmailDesconectar: () => request('/correos/gmail/desconectar', { method: 'POST' }),
  gmailEtiqueta: (etiqueta) => request(`/correos/gmail/etiqueta?etiqueta=${encodeURIComponent(etiqueta)}`, { method: 'POST' }),
  // params: { completa: true } fuerza la ventana larga (90 días); cada llamada procesa un lote.
  sincronizarCorreos: (params) =>
    request(`/correos/sincronizar${params?.completa ? '?completa=true' : ''}`, { method: 'POST' }),
  correosLista: (filtro = 'nuevos', offset = 0, limite = 30) =>
    request(`/correos/lista?filtro=${filtro}&limite=${limite}&offset=${offset}`),
  conexionesEstado: () => request('/conexiones/estado'),
  // Pantalla Sincronización: grilla cuentas x meses, tareas y cola de categorías por preguntar.
  sincronizacionEstado: () => request('/sincronizacion/estado'),
  sincronizacionPorCategorizar: (offset = 0, limite = 10) =>
    request(`/sincronizacion/por-categorizar?limite=${limite}&offset=${offset}`),
  correosPendientes: () => request('/correos/pendientes'),
  editarCorreo: (id, data) => request(`/correos/${id}`, { method: 'PATCH', body: data }),
  aprobarCorreo: (id, cuentaId, extra = {}) => request(`/correos/${id}/aprobar`, { method: 'POST', body: { cuenta_id: cuentaId, ...extra } }),
  descartarCorreo: (id) => request(`/correos/${id}/descartar`, { method: 'POST' }),
  extractosCorreo: (estado, offset = 0, limite = 50) =>
    request(`/correos/extractos?limite=${limite}&offset=${offset}${estado ? `&estado=${estado}` : ''}`),
  conciliarExtractoCorreo: (id, cuentaId) =>
    request(`/correos/extractos/${id}/conciliar`, { method: 'POST', body: { cuenta_id: cuentaId } }),
  descartarExtractoCorreo: (id) => request(`/correos/extractos/${id}/descartar`, { method: 'POST' }),
  clavePdfEstado: () => request('/correos/clave-pdf'),
  guardarClavePdf: (clave) => request('/correos/clave-pdf', { method: 'PUT', body: { clave } }),
  borrarClavePdf: () => request('/correos/clave-pdf', { method: 'DELETE' }),

  resumenSemanal: (desde, hasta) =>
    request(`/insights/resumen-semanal${desde && hasta ? `?desde=${desde}&hasta=${hasta}` : ''}`),
  // Informe "en qué gasto": p = { periodo, desde, hasta, mes }
  informeGasto: (p = {}) => request(`/informes/gasto?${new URLSearchParams(limpiar(p)).toString()}`),
  informeMovimientos: (p = {}) => request(`/informes/gasto/movimientos?${new URLSearchParams(limpiar(p)).toString()}`),
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
  impuestosExcel: (anio) => descargarArchivo(`/impuestos/exportar.xlsx?anio=${anio}`, `cuadrame_renta_${anio}.xlsx`),

  // Cierre de mes
  cierresMes: () => request('/cierre-mes'),
  cierreMes: (mes) => request(`/cierre-mes/${mes}`),
  generarCierreMes: (mes) => request(`/cierre-mes/${mes}/generar`, { method: 'POST' }),
  cierrePreferencias: () => request('/cierre-mes/preferencias'),
  guardarCierrePreferencias: (correo) => request('/cierre-mes/preferencias', { method: 'PUT', body: { correo } }),
}
