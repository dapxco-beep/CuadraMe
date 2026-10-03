// Pantalla Correos: sección "Extractos encontrados", clave del PDF y privacidad.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const CUENTAS = [
  { id: 'c1', nombre: 'Efectivo', saldo: 0, moneda: 'COP', tipo: 'efectivo', icono: '💵' },
  { id: 'c2', nombre: 'Bancolombia Ahorros', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
]

const EXTRACTOS = [
  { id: 'e1', banco: 'Bancolombia', periodo: '01/09/2026 a 30/09/2026', asunto: 'Tu extracto', archivo: 'a.pdf', estado: 'nuevo', cuenta_sugerida_id: 'c2', historial_id: null },
  { id: 'e2', banco: 'Davivienda', periodo: 'agosto 2026', asunto: 'Extracto', archivo: 'b.pdf', estado: 'falta_clave', cuenta_sugerida_id: null, historial_id: null },
  { id: 'e3', banco: 'Nequi', periodo: 'julio 2026', asunto: 'Extracto', archivo: 'c.pdf', estado: 'procesado', cuenta_sugerida_id: null, historial_id: 'h9' },
]

const api = vi.hoisted(() => ({
  gmailEstado: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  guardarClavePdf: vi.fn(),
  borrarClavePdf: vi.fn(),
  conciliarExtractoCorreo: vi.fn(),
  descartarExtractoCorreo: vi.fn(),
  sincronizarCorreos: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import Correos from '../screens/Correos'

function Destino() {
  const loc = useLocation()
  return <p>Destino conciliación {loc.state?.historialId}</p>
}

function montar() {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={['/correos']}>
        <Routes>
          <Route path="/correos" element={<Correos />} />
          <Route path="/conciliacion" element={<Destino />} />
        </Routes>
      </MemoryRouter>
    </DialogosProvider>
  )
}

beforeEach(() => {
  localStorage.clear()
  Object.values(api).forEach((f) => f.mockReset())
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', etiqueta: 'gastos' })
  api.correosPendientes.mockResolvedValue([])
  api.extractosCorreo.mockResolvedValue(EXTRACTOS)
  api.clavePdfEstado.mockResolvedValue({ configurada: false })
  api.sincronizarCorreos.mockResolvedValue({ ok: true, nuevos: 0, omitidos: 0, extractos_nuevos: 0 })
})

describe('Correos: extractos encontrados', () => {
  it('lista los extractos con su estado y el mensaje de privacidad', async () => {
    montar()
    expect(await screen.findByText('Extractos encontrados (3)')).toBeTruthy()
    expect(screen.getByText('Nuevo')).toBeTruthy()
    expect(screen.getByText('Falta clave')).toBeTruthy()
    expect(screen.getByText('Procesado')).toBeTruthy()
    expect(screen.getByText(/solo tiene permiso de/i)).toBeTruthy()
    expect(screen.getByText(/No guardamos tus correos ni los PDF/i)).toBeTruthy()
  })

  it('un extracto sin clave no se puede conciliar', async () => {
    montar()
    await screen.findByText('Davivienda')
    const botones = screen.getAllByRole('button', { name: 'Conciliar' })
    expect(botones[0].disabled).toBe(false) // el nuevo
    expect(botones[1].disabled).toBe(true) // falta clave
    expect(screen.getByText(/falta la clave del PDF/i)).toBeTruthy()
  })

  it('Conciliar usa la cuenta sugerida y abre el flujo de conciliación con el historial', async () => {
    api.conciliarExtractoCorreo.mockResolvedValue({ ok: true, historial_id: 'h1' })
    montar()
    await screen.findByText('Bancolombia')
    fireEvent.click(screen.getAllByRole('button', { name: 'Conciliar' })[0])
    await waitFor(() => expect(api.conciliarExtractoCorreo).toHaveBeenCalledWith('e1', 'c2'))
    expect(await screen.findByText('Destino conciliación h1')).toBeTruthy()
  })

  it('si la conciliación falla muestra el mensaje y se queda en la pantalla', async () => {
    api.conciliarExtractoCorreo.mockResolvedValue({ ok: false, error: 'No se pudo leer este PDF.' })
    montar()
    await screen.findByText('Bancolombia')
    fireEvent.click(screen.getAllByRole('button', { name: 'Conciliar' })[0])
    expect(await screen.findByText('No se pudo leer este PDF.')).toBeTruthy()
  })

  it('permite guardar la clave del PDF sin mostrarla de vuelta', async () => {
    api.guardarClavePdf.mockResolvedValue({ ok: true, configurada: true })
    montar()
    await screen.findByText('Bancolombia')
    fireEvent.click(screen.getByRole('button', { name: /Clave del PDF/ }))
    expect(screen.getByText('Aún no hay clave guardada.')).toBeTruthy()
    const campo = screen.getByLabelText('Clave del PDF')
    expect(campo.type).toBe('password')
    fireEvent.change(campo, { target: { value: '1020304050' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(api.guardarClavePdf).toHaveBeenCalledWith('1020304050'))
    expect(await screen.findByText('Hay una clave guardada.')).toBeTruthy()
    expect(screen.queryByDisplayValue('1020304050')).toBeNull()
  })

  it('sincroniza sola al abrir si pasaron más de 6 horas, y no si fue reciente', async () => {
    montar()
    await waitFor(() => expect(api.sincronizarCorreos).toHaveBeenCalledTimes(1))
    expect(Number(localStorage.getItem('cuadrame_gmail_sync'))).toBeGreaterThan(0)
  })

  it('no vuelve a sincronizar si ya se hizo hace poco', async () => {
    localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
    montar()
    await screen.findByText('Extractos encontrados (3)')
    expect(api.sincronizarCorreos).not.toHaveBeenCalled()
  })
})
