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

export const api = {
  cuentas: () => request('/cuentas'),
  crearCuenta: (data) => request('/cuentas', { method: 'POST', body: data }),

  movimientos: (limit = 100) => request(`/movimientos?limit=${limit}`),
  crearMovimiento: (data) => request('/movimientos', { method: 'POST', body: data }),
  eliminarMovimiento: (id) => request(`/movimientos/${id}`, { method: 'DELETE' }),
  clasificar: (data) => request('/movimientos/clasificar', { method: 'POST', body: data }),

  presupuestos: () => request('/presupuestos'),
  crearPresupuesto: (data) => request('/presupuestos', { method: 'POST', body: data }),
  eliminarPresupuesto: (id) => request(`/presupuestos/${id}`, { method: 'DELETE' }),

  reporteMensual: (mes) => request(`/reportes/mensual${mes ? `?mes=${mes}` : ''}`),

  plan: () => request('/pagos/plan'),
  crearCheckout: (successUrl, cancelUrl) =>
    request(
      `/pagos/checkout?success_url=${encodeURIComponent(successUrl)}&cancel_url=${encodeURIComponent(cancelUrl)}`,
      { method: 'POST' }
    ),

  metas: () => request('/metas'),
  crearMeta: (data) => request('/metas', { method: 'POST', body: data }),
  aportarMeta: (id, monto) => request(`/metas/${id}/aportar?monto=${monto}`, { method: 'POST' }),
  eliminarMeta: (id) => request(`/metas/${id}`, { method: 'DELETE' }),

  recurrentes: () => request('/recurrentes'),
  crearRecurrente: (data) => request('/recurrentes', { method: 'POST', body: data }),
  marcarRecurrentePagado: (id, crearMovimiento = true) =>
    request(`/recurrentes/${id}/marcar_pagado`, { method: 'POST', body: { crear_movimiento: crearMovimiento } }),
  eliminarRecurrente: (id) => request(`/recurrentes/${id}`, { method: 'DELETE' }),

  deudas: () => request('/deudas'),
  crearDeuda: (data) => request('/deudas', { method: 'POST', body: data }),
  pagarDeuda: (id, montoPagado, crearMovimiento = true) =>
    request(`/deudas/${id}/pagar`, { method: 'POST', body: { monto_pagado: montoPagado, crear_movimiento: crearMovimiento } }),
  eliminarDeuda: (id) => request(`/deudas/${id}`, { method: 'DELETE' }),
}
