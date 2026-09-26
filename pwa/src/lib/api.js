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
}
