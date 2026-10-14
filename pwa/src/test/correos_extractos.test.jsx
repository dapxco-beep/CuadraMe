// Centro Traer movimientos, bloque «Desde tu correo»: extractos encontrados, clave del PDF y privacidad.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [
  { id: 'c1', nombre: 'Efectivo', saldo: 0, moneda: 'COP', tipo: 'efectivo', icono: '💵' },
  { id: 'c2', nombre: 'Bancolombia Ahorros', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
]

const EXTRACTOS = [
  { id: 'e1', banco: 'Bancolombia', periodo: '01/09/2026 a 30/09/2026', asunto: 'Tu extracto', archivo: 'a.pdf', estado: 'nuevo', cuenta_sugerida_id: 'c2', historial_id: null },
  { id: 'e2', banco: 'Davivienda', periodo: 'agosto 2026', asunto: 'Extracto', archivo: 'b.pdf', estado: 'falta_clave', cuenta_sugerida_id: null, historial_id: null },
  { id: 'e3', banco: 'Nequi', periodo: 'julio 2026', asunto: 'Extracto', archivo: 'c.pdf', estado: 'procesado', cuenta_sugerida_id: null, historial_id: 'h9' },
]

const ESTADO = {
  meses: [], cuentas: [], sin_cuenta: [], ultima_sync: null,
  tareas: [
    { id: 'falta_clave', titulo: 'Falta la clave del PDF', detalle: '', cantidad: 1, ruta: '/sincronizacion#clave' },
    { id: 'extractos_por_conciliar', titulo: 'Extractos por conciliar', detalle: '', cantidad: 1, ruta: '/sincronizacion#extractos' },
  ],
}

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  guardarClavePdf: vi.fn(),
  borrarClavePdf: vi.fn(),
  conciliarExtractoCorreo: vi.fn(),
  descartarExtractoCorreo: vi.fn(),
  sincronizarCorreos: vi.fn(),
  obtenerReviewExtracto: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ nombres: ['Otros'], iconoDe: () => '' }) }))

import { DialogosProvider } from '../lib/DialogosContext'
import Sincronizacion from '../screens/Sincronizacion'

function montar() {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={['/sincronizacion']}>
        <Routes>
          <Route path="/sincronizacion" element={<Sincronizacion />} />
        </Routes>
      </MemoryRouter>
    </DialogosProvider>
  )
}

const extractosEncontrados = () => screen.findByRole('heading', { level: 3, name: /Extractos para conciliar/ })

beforeEach(() => {
  localStorage.clear()
  Object.values(api).forEach((f) => f.mockReset())
  api.sincronizacionEstado.mockResolvedValue(ESTADO)
  api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', etiqueta: 'gastos' })
  api.correosPendientes.mockResolvedValue([])
  api.extractosCorreo.mockResolvedValue(EXTRACTOS)
  api.clavePdfEstado.mockResolvedValue({ configurada: false })
  api.sincronizarCorreos.mockResolvedValue({ ok: true, nuevos: 0, omitidos: 0, extractos_nuevos: 0 })
})

describe('Desde tu correo: extractos encontrados', () => {
  it('lista los extractos con su estado y el mensaje de privacidad', async () => {
    montar()
    // El conciliado (Nequi) no cuenta como pendiente: queda en su sección plegada.
    expect((await extractosEncontrados()).textContent).toBe('Extractos para conciliar2')
    expect(within(screen.getByTestId('extracto-e1')).getByText('Nuevo · listo para revisar')).toBeTruthy()
    expect(within(screen.getByTestId('extracto-e2')).getByText('Falta la clave del PDF')).toBeTruthy()
    expect(screen.queryByText(/Nequi/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Extractos ya revisados \(1\)/ }))
    expect(screen.getByText(/Nequi · julio 2026/)).toBeTruthy()
    // El mensaje de privacidad vive en «Conexión de Gmail» (plegada por defecto): se abre para leerlo.
    fireEvent.click(screen.getByTestId('bloque-sinc-conexion').querySelector('h2 button'))
    expect(screen.getByText(/Solo tengo permiso de/)).toBeTruthy()
    expect(screen.getByText(/No guardo tus correos ni los PDF/)).toBeTruthy()
  })

  it('un extracto sin clave no se puede conciliar: ofrece poner la clave', async () => {
    montar()
    await extractosEncontrados()
    const sinClave = screen.getByTestId('extracto-e2')
    expect(within(sinClave).queryByRole('button', { name: 'Revisar extracto' })).toBeNull()
    expect(within(sinClave).getByRole('button', { name: 'Poner clave' })).toBeTruthy()
    expect(within(screen.getByTestId('extracto-e1')).getByRole('button', { name: 'Revisar extracto' }).disabled).toBe(false)
  })

  it('Conciliar usa la cuenta sugerida y abre la revisión del historial en el mismo centro', async () => {
    api.conciliarExtractoCorreo.mockResolvedValue({ ok: true, historial_id: 'h1' })
    api.obtenerReviewExtracto.mockResolvedValue({ ok: true, historial_id: 'h1', cuenta_id: 'c2', banco_detectado: 'Bancolombia', total_movimientos: 0, review: [] })
    montar()
    await extractosEncontrados()
    fireEvent.click(within(screen.getByTestId('extracto-e1')).getByRole('button', { name: 'Revisar extracto' }))
    await waitFor(() => expect(api.conciliarExtractoCorreo).toHaveBeenCalledWith('e1', 'c2'))
    expect(await screen.findByTestId('revision-multiple')).toBeTruthy()
    expect(api.obtenerReviewExtracto).toHaveBeenCalledWith('h1')
  })

  it('si la conciliación falla muestra el mensaje y se queda en la pantalla', async () => {
    api.conciliarExtractoCorreo.mockResolvedValue({ ok: false, error: 'No se pudo leer este PDF.' })
    montar()
    await extractosEncontrados()
    fireEvent.click(within(screen.getByTestId('extracto-e1')).getByRole('button', { name: 'Revisar extracto' }))
    expect(await screen.findByText('No se pudo leer este PDF.')).toBeTruthy()
  })

  it('permite guardar la clave del PDF sin mostrarla de vuelta, y borrarla', async () => {
    api.guardarClavePdf.mockResolvedValue({ ok: true, configurada: true })
    api.borrarClavePdf.mockResolvedValue({ ok: true, configurada: false })
    montar()
    await extractosEncontrados()
    expect(screen.getByText(/Normalmente es tu cédula/)).toBeTruthy()
    const campo = screen.getByLabelText('Clave del PDF')
    expect(campo.type).toBe('password')
    fireEvent.change(campo, { target: { value: '1020304050' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(api.guardarClavePdf).toHaveBeenCalledWith('1020304050'))
    expect(await screen.findByText(/Hay una clave guardada/)).toBeTruthy()
    expect(screen.queryByDisplayValue('1020304050')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Borrar la clave guardada' }))
    await waitFor(() => expect(api.borrarClavePdf).toHaveBeenCalled())
  })

  it('sincroniza sola al abrir si pasaron más de 6 horas, y no si fue reciente', async () => {
    montar()
    await waitFor(() => expect(api.sincronizarCorreos).toHaveBeenCalledTimes(1))
    expect(Number(localStorage.getItem('cuadrame_gmail_sync'))).toBeGreaterThan(0)
  })

  it('no vuelve a sincronizar si ya se hizo hace poco', async () => {
    localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
    montar()
    await extractosEncontrados()
    expect(api.sincronizarCorreos).not.toHaveBeenCalled()
  })
})
