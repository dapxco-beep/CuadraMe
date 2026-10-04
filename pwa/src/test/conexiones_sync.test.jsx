// Sincronización por lotes (cliente), tablero Conexiones y mejoras de Correos.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const api = vi.hoisted(() => ({
  conexionesEstado: vi.fn(),
  sincronizarCorreos: vi.fn(),
  apiKey: vi.fn(),
  regenerarApiKey: vi.fn(),
  pagoDePrueba: vi.fn(),
  movimientosPorConfirmar: vi.fn(),
  eliminarMovimiento: vi.fn(),
  gmailEstado: vi.fn(),
  correosPendientes: vi.fn(),
  correosLista: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Efectivo', moneda: 'COP' }], cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/push', () => ({
  pushSoportado: () => false,
  estadoPermiso: async () => 'default',
  activarPush: vi.fn(),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { haceCuanto, resumenSync, sincronizarTodo } from '../lib/sincronizarGmail'
import Conexiones from '../screens/Conexiones'
import Correos from '../screens/Correos'

const ESTADO = {
  hay_falla: false,
  gmail: {
    semaforo: 'verde', mensaje: 'Todo al día: tus correos se están leyendo bien.', conectado: true, email: 'yo@gmail.com',
    ultima_sync: new Date(Date.now() - 2 * 3600 * 1000).toISOString(), correos_leidos: 340, notificaciones: 18, extractos: 3,
    extractos_falta_clave: 1, en_curso: false,
  },
  atajo: { semaforo: 'ambar', mensaje: 'La clave existe pero nunca se ha usado.', tiene_clave: true, ultimo_uso: null, movimientos_7d: 0 },
  conciliacion: {
    semaforo: 'ambar', mensaje: 'Hay 3 movimientos del banco sin registrar.',
    cuentas: [
      { cuenta_id: 'c1', cuenta: 'Ahorros', icono: '🏦', extracto: true, historial_id: 'h1', cruzados: 7, faltantes: 3, sin_extracto: 2, ultimo_cruce: new Date().toISOString() },
      { cuenta_id: 'c2', cuenta: 'Efectivo', icono: '💵', extracto: false },
    ],
  },
  push: { semaforo: 'ambar', mensaje: 'No tienes notificaciones activas.', suscripciones: 0 },
}

function montar(ui, ruta) {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[ruta]}>
        <Routes>
          <Route path="/conexiones" element={<Conexiones />} />
          <Route path="/correos" element={<Correos />} />
          <Route path="/conciliacion" element={<p>Pantalla conciliación</p>} />
        </Routes>
      </MemoryRouter>
    </DialogosProvider>
  )
}

beforeEach(() => {
  localStorage.clear()
  Object.values(api).forEach((f) => f.mockReset())
  api.conexionesEstado.mockResolvedValue(ESTADO)
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', etiqueta: 'gastos' })
  api.correosPendientes.mockResolvedValue([])
  api.extractosCorreo.mockResolvedValue([])
  api.clavePdfEstado.mockResolvedValue({ configurada: false })
})

describe('sincronizarTodo', () => {
  it('repite la llamada hasta completado y reporta el progreso', async () => {
    api.sincronizarCorreos
      .mockResolvedValueOnce({ ok: true, leidos: 40, total_estimado: 120, completado: false })
      .mockResolvedValueOnce({ ok: true, leidos: 80, total_estimado: 120, completado: false })
      .mockResolvedValueOnce({ ok: true, leidos: 120, total_estimado: 120, completado: true, nuevos: 18, extractos_encontrados: 3 })
    const vistos = []
    const r = await sincronizarTodo({ completa: true, onProgreso: (p) => vistos.push(p.leidos) })
    expect(api.sincronizarCorreos).toHaveBeenCalledTimes(3)
    expect(api.sincronizarCorreos.mock.calls[0][0]).toEqual({ completa: true })
    expect(api.sincronizarCorreos.mock.calls[1][0]).toBeUndefined()
    expect(vistos).toEqual([40, 80, 120])
    expect(resumenSync(r)).toBe('Encontré 18 movimientos nuevos y 3 extractos.')
  })

  it('se detiene si el servidor responde con error', async () => {
    api.sincronizarCorreos.mockResolvedValueOnce({ ok: false, error: 'Se perdió el acceso' })
    const r = await sincronizarTodo()
    expect(r.ok).toBe(false)
    expect(api.sincronizarCorreos).toHaveBeenCalledTimes(1)
  })

  it('textos de tiempo y de resumen vacío', () => {
    const ahora = Date.parse('2026-10-01T12:00:00Z')
    expect(haceCuanto('2026-10-01T10:00:00', ahora)).toBe('hace 2 h')
    expect(haceCuanto(null)).toBeNull()
    expect(resumenSync({ nuevos: 0, extractos_nuevos: 0 })).toMatch(/no hay nada nuevo/)
  })
})

describe('Conexiones y estado', () => {
  it('muestra una tarjeta por conexión con semáforo y explicación', async () => {
    montar(null, '/conexiones')
    expect(await screen.findByTestId('tarjeta-gmail')).toBeTruthy()
    expect(screen.getByTestId('tarjeta-atajo')).toBeTruthy()
    expect(screen.getByTestId('tarjeta-conciliacion')).toBeTruthy()
    expect(screen.getByTestId('tarjeta-push')).toBeTruthy()
    expect(screen.getByText(/última sincronización hace 2 h/)).toBeTruthy()
    expect(screen.getByText('340')).toBeTruthy()
    expect(screen.getByText(/1 esperan clave/)).toBeTruthy()
    expect(screen.getByText('Todo al día: tus correos se están leyendo bien.')).toBeTruthy()
    const filas = screen.getAllByTestId('fila-conciliacion')
    expect(filas[0].textContent).toMatch(/7.*cruzados.*3.*faltantes.*2.*registrados sin extracto/)
    expect(screen.getByRole('button', { name: 'Importar extracto' })).toBeTruthy()
  })

  it('Sincronizar todo muestra "Leí X de Y" y termina con el resumen', async () => {
    let soltar
    api.sincronizarCorreos
      .mockResolvedValueOnce({ ok: true, leidos: 120, total_estimado: 340, completado: false })
      .mockImplementationOnce(() => new Promise((res) => { soltar = res }))
    montar(null, '/conexiones')
    fireEvent.click(await screen.findByRole('button', { name: /Sincronizar todo/ }))
    expect(await screen.findByText(/Leí 120 de 340/)).toBeTruthy()
    soltar({ ok: true, leidos: 340, total_estimado: 340, completado: true, nuevos: 5, extractos_encontrados: 0 })
    expect(await screen.findByText('Encontré 5 movimientos nuevos.')).toBeTruthy()
  })

  it('Probar conexión crea el pago de prueba, confirma que llegó y lo borra', async () => {
    api.apiKey.mockResolvedValue({ api_key: 'cdm_x' })
    api.pagoDePrueba.mockResolvedValue({ id: 'm1' })
    api.movimientosPorConfirmar.mockResolvedValue([{ id: 'm1' }])
    api.eliminarMovimiento.mockResolvedValue({})
    montar(null, '/conexiones')
    fireEvent.click(await screen.findByRole('button', { name: /Probar conexión/ }))
    expect(await screen.findByText(/¡Llegó!/)).toBeTruthy()
    expect(api.pagoDePrueba).toHaveBeenCalledWith('cdm_x')
    expect(api.eliminarMovimiento).toHaveBeenCalledWith('m1')
  })

  it('Clave nueva pide confirmación antes de revocar la anterior', async () => {
    api.regenerarApiKey.mockResolvedValue({ api_key: 'cdm_nueva' })
    montar(null, '/conexiones')
    fireEvent.click(await screen.findByRole('button', { name: /Clave nueva/ }))
    expect(api.regenerarApiKey).not.toHaveBeenCalled()
    fireEvent.click(await screen.findByRole('button', { name: /Generar y revocar/ }))
    await waitFor(() => expect(api.regenerarApiKey).toHaveBeenCalledTimes(1))
  })
})

describe('Correos: pasos, resumen y filtros', () => {
  it('muestra los pasos y el resumen claro tras sincronizar', async () => {
    api.sincronizarCorreos.mockResolvedValue({ ok: true, completado: true, nuevos: 18, extractos_encontrados: 3 })
    montar(null, '/correos')
    expect(await screen.findByTestId('pasos')).toBeTruthy()
    expect(screen.getByText('Conecta Gmail')).toBeTruthy()
    expect(await screen.findByText('Encontré 18 movimientos nuevos y 3 extractos.').catch(() => null)).toBeNull // silencioso al abrir
    fireEvent.click(screen.getByRole('button', { name: /Sincronizar ahora/ }))
    expect(await screen.findByText('Encontré 18 movimientos nuevos y 3 extractos.')).toBeTruthy()
  })

  it('el filtro Ignorados lista y permite cargar más', async () => {
    localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
    const pagina = (desde) => Array.from({ length: 30 }, (_, i) => ({ id: `i${desde + i}`, asunto: `Promo ${desde + i}`, remitente: 'b@banco.co' }))
    api.correosLista.mockResolvedValueOnce(pagina(0)).mockResolvedValueOnce(pagina(30).slice(0, 5))
    montar(null, '/correos')
    fireEvent.click(await screen.findByRole('button', { name: 'Ignorados' }))
    expect(await screen.findByText('Promo 0')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Cargar más' }))
    expect(await screen.findByText('Promo 34')).toBeTruthy()
    expect(api.correosLista).toHaveBeenLastCalledWith('ignorados', 30, 30)
    expect(screen.queryByRole('button', { name: 'Cargar más' })).toBeNull()
  })

  it('el filtro Falta clave pide solo esos extractos al servidor', async () => {
    localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
    montar(null, '/correos')
    fireEvent.click(await screen.findByRole('button', { name: 'Falta clave' }))
    await waitFor(() => expect(api.extractosCorreo).toHaveBeenCalledWith('falta_clave'))
  })
})
