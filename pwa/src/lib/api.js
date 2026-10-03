import { supabase } from './supabase'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth) {
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    if (token) headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Error ${res.status}`)
  }
  return res.json()
}

async function descargarArchivo(path, nombreArchivo) {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const res = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error(`Error ${res.status}`)

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nombreArchivo
  a.click()
  URL.revokeObjectURL(url)
}

export const api = {
  cuentas: () => request('/cuentas'),
  crearCuenta: (data) => request('/cuentas', { method: 'POST', body: data }),
  editarCuenta: (id, data) => request(`/cuentas/${id}`, { method: 'PUT', body: data }),
  eliminarCuenta: (id) => request(`/cuentas/${id}`, { method: 'DELETE' }),

  movimientos: (limit = 100, offset = 0) => request(`/movimientos?limit=${limit}&offset=${offset}`),
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

  procesarExtracto: (pdfBase64, cuentaId, password = '') =>
    request('/conciliacion/procesar', {
      method: 'POST',
      body: { pdf_base64: pdfBase64, cuenta_id: cuentaId, password },
    }),
  historialExtractos: () => request('/conciliacion/historial'),
  obtenerReviewExtracto: (id) => request(`/conciliacion/historial/${id}`),
  importarFaltantes: (id, fingerprints, categorias) =>
    request(`/conciliacion/historial/${id}/importar`, {
      method: 'POST',
      body: { fingerprints, categorias },
    }),
  eliminarHistorialExtracto: (id) => request(`/conciliacion/historial/${id}`, { method: 'DELETE' }),

  categorias: (incluirInactivas = false) =>
    request(`/categorias${incluirInactivas ? '?incluir_inactivas=true' : ''}`),
  crearCategoria: (data) => request('/categorias', { method: 'POST', body: data }),
  editarCategoria: (id, data) => request(`/categorias/${id}`, { method: 'PUT', body: data }),
  eliminarCategoria: (id) => request(`/categorias/${id}`, { method: 'DELETE' }),

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
  sincronizarCorreos: () => request('/correos/sincronizar', { method: 'POST' }),
  correosPendientes: () => request('/correos/pendientes'),
  editarCorreo: (id, data) => request(`/correos/${id}`, { method: 'PATCH', body: data }),
  aprobarCorreo: (id, cuentaId) => request(`/correos/${id}/aprobar`, { method: 'POST', body: { cuenta_id: cuentaId } }),
  descartarCorreo: (id) => request(`/correos/${id}/descartar`, { method: 'POST' }),
  extractosCorreo: () => request('/correos/extractos'),
  conciliarExtractoCorreo: (id, cuentaId) =>
    request(`/correos/extractos/${id}/conciliar`, { method: 'POST', body: { cuenta_id: cuentaId } }),
  descartarExtractoCorreo: (id) => request(`/correos/extractos/${id}/descartar`, { method: 'POST' }),
  clavePdfEstado: () => request('/correos/clave-pdf'),
  guardarClavePdf: (clave) => request('/correos/clave-pdf', { method: 'PUT', body: { clave } }),
  borrarClavePdf: () => request('/correos/clave-pdf', { method: 'DELETE' }),

  resumenSemanal: () => request('/insights/resumen-semanal'),
  edadDelDinero: () => request('/insights/edad-del-dinero'),
  saludFinanciera: () => request('/insights/salud-financiera'),
  wrapped: (mes) => request(`/reportes/wrapped${mes ? `?mes=${mes}` : ''}`),
  alertasProactivas: () => request('/insights/alertas-proactivas'),
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
}
