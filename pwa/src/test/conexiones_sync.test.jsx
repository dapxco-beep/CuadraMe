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
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ nombres: ['Otros'], iconoDe: () => '' }) }))
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
import Sincronizacion from '../screens/Sincronizacion'

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
          <Route path="/sincronizacion" element={<Sincronizacion />} />
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
    expect(screen.getByText(/última vez hace 2 h/)).toBeTruthy()
    expect(screen.getByText('340')).toBeTruthy()
    expect(screen.getByText(/1 esperan clave/)).toBeTruthy()
    expect(screen.getByText('Todo al día: tus correos se están leyendo bien.')).toBeTruthy()
    const filas = screen.getAllByTestId('fila-conciliacion')
    expect(filas[0].textContent).toMatch(/7.*coinciden.*3.*faltan por registrar.*2.*sin extracto/)
    expect(screen.getByRole('button', { name: 'Importar extracto' })).toBeTruthy()
  })

  it('Traer todo ahora muestra "Leí X de Y" y termina con el resumen', async () => {
    let soltar
    api.sincronizarCorreos
      .mockResolvedValueOnce({ ok: true, leidos: 120, total_estimado: 340, completado: false })
      .mockImplementationOnce(() => new Promise((res) => { soltar = res }))
    montar(null, '/conexiones')
    fireEvent.click(await screen.findByRole('button', { name: /Traer todo ahora/ }))
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
    expect(api.pagoDePrueba).toHaveBeenCalledWith(undefined)  // sin leer la clave guardada: la prueba usa la sesión
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

describe('Centro: pasos, resumen y correos ignorados', () => {
  beforeEach(() => {
    localStorage.setItem('cuadrame_gmail_sync', String(Date.now())) // sin sincronización automática al abrir
    api.sincronizacionEstado.mockResolvedValue({ meses: [], cuentas: [], sin_cuenta: [], tareas: [], ultima_sync: null })
    api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
  })

  it('muestra los pasos Conecta, Trae, Revisa y el resumen claro tras sincronizar', async () => {
    // «Traer todo» lee cada uso por separado: movimientos por un lado, extractos por el otro.
    api.sincronizarCorreos.mockImplementation(async (p) => (p?.tipo === 'extractos'
      ? { ok: true, completado: true, extractos_encontrados: 3, tipo: 'extractos' }
      : { ok: true, completado: true, nuevos: 18, tipo: 'movimientos' }))
    montar(null, '/sincronizacion')
    expect(await screen.findByTestId('pasos')).toBeTruthy()
    expect(screen.getByText('Conecta')).toBeTruthy()
    expect(screen.getByText('Revisa')).toBeTruthy()
    // Conectado y sin datos: va en el paso 2.
    expect(screen.getByText('Trae').closest('li').getAttribute('aria-current')).toBe('step')
    fireEvent.click(screen.getByRole('button', { name: 'Traer todo ahora' }))
    expect(await screen.findByText(/Encontré 18 movimientos nuevos y 3 extractos\./)).toBeTruthy()
  })

  it('«Ver correos ignorados» los lista', async () => {
    api.correosLista.mockResolvedValue([{ id: 'i1', asunto: 'Promo 0', remitente: 'b@banco.co' }])
    montar(null, '/sincronizacion')
    // Sin tareas en «Movimientos», la sección arranca plegada: se abre antes de buscar el enlace.
    await screen.findByTestId('pasos').catch(() => null)
    const bm = (await screen.findAllByRole('button')).find((x) => x.getAttribute('aria-expanded') === 'false' && /^Movimientos/.test(x.textContent.trim()))
    if (bm) fireEvent.click(bm)
    fireEvent.click(await screen.findByRole('button', { name: 'Ver correos ignorados' }))
    expect(await screen.findByText('Promo 0')).toBeTruthy()
    expect(api.correosLista).toHaveBeenCalledWith('ignorados', 0, 30)
  })
})
