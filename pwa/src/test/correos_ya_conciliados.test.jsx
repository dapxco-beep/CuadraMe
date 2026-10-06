// Correos: lo ya conciliado no es pendiente (sección plegada) y al aprobar un correo
// con otra categoría se recuerda la regla del comercio.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [{ id: 'bc', nombre: 'Bancolombia Ahorros', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]

const EXTRACTOS = [
  { id: 'e1', banco: 'Bancolombia', periodo: 'octubre 2026', asunto: 'Extracto', archivo: 'a.pdf', estado: 'nuevo', cuenta_sugerida_id: 'bc', historial_id: null },
  { id: 'e2', banco: 'Nu Colombia', periodo: 'septiembre 2026', asunto: 'Extracto', archivo: 'b.pdf', estado: 'ya_conciliado', cuenta_sugerida_id: 'bc', historial_id: null, cruzados: 12 },
  { id: 'e3', banco: 'Nequi', periodo: 'agosto 2026', asunto: 'Extracto', archivo: 'c.pdf', estado: 'procesado', cuenta_sugerida_id: null, historial_id: 'h9', cruzados: 1 },
]

const api = vi.hoisted(() => ({
  gmailEstado: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  aprobarCorreo: vi.fn(),
  conciliarExtractoCorreo: vi.fn(),
  sincronizarCorreos: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Hogar', 'Otros'], iconoDe: () => '' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import Correos from '../screens/Correos'

function montar() {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={['/correos']}>
        <Routes>
          <Route path="/correos" element={<Correos />} />
          <Route path="/conciliacion" element={<p>Pantalla conciliación</p>} />
        </Routes>
      </MemoryRouter>
    </DialogosProvider>
  )
}

const CORREO = {
  id: 'k1', comercio: 'Zafiro Quimera', asunto: 'Compra aprobada', categoria_sugerida: 'Comida', tipo_sugerido: 'expense',
  monto: 15000, banco_detectado: 'Bancolombia', cuenta_sugerida_id: 'bc', falta_cuenta: false,
  razon_categoria: 'por palabra clave «zafiro»', preguntar_categoria: false,
}

beforeEach(() => {
  localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
  Object.values(api).forEach((f) => f.mockReset())
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', etiqueta: 'gastos' })
  api.correosPendientes.mockResolvedValue([])
  api.extractosCorreo.mockResolvedValue(EXTRACTOS)
  api.clavePdfEstado.mockResolvedValue({ configurada: false })
  api.aprobarCorreo.mockResolvedValue({})
})

describe('Correos: extractos ya conciliados', () => {
  it('no cuentan ni aparecen como nuevos: quedan en una sección plegada con sus movimientos cruzados', async () => {
    montar()
    expect(await screen.findByText('Extractos encontrados (1)')).toBeTruthy()
    expect(screen.getAllByText('Nuevo')).toHaveLength(1)
    expect(screen.queryByText('Nu Colombia')).toBeNull()

    const boton = screen.getByRole('button', { name: /Ya conciliados \(2\)/ })
    expect(boton.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(boton)
    const fila = screen.getByTestId('conciliado-e2')
    expect(within(fila).getByText(/Nu Colombia · septiembre 2026/)).toBeTruthy()
    expect(within(fila).getByText(/Bancolombia Ahorros · 12 movimientos cruzados/)).toBeTruthy()
    expect(within(screen.getByTestId('conciliado-e3')).getByText('1 movimiento cruzado')).toBeTruthy()
  })

  it('el filtro "Ya conciliados" muestra solo esos, ya abiertos, y "Revisar de nuevo" no bloquea', async () => {
    api.conciliarExtractoCorreo.mockResolvedValue({ ok: true, historial_id: 'h1' })
    montar()
    await screen.findByText('Extractos encontrados (1)')
    fireEvent.click(screen.getByRole('button', { name: 'Ya conciliados', pressed: false }))
    expect(await screen.findByText('Extractos ya conciliados')).toBeTruthy()
    expect(screen.getByTestId('conciliado-e2')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Conciliar' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Revisar de nuevo' }))
    await waitFor(() => expect(api.conciliarExtractoCorreo).toHaveBeenCalledWith('e2', 'bc'))
    expect(await screen.findByText('Pantalla conciliación')).toBeTruthy()
  })
})

describe('Correos: aprender la regla al aprobar', () => {
  it('muestra la razón de la categoría y, si la cambia, deja «Recordar» marcado y lo envía', async () => {
    api.correosPendientes.mockResolvedValue([CORREO])
    api.extractosCorreo.mockResolvedValue([])
    montar()
    await screen.findByText('Zafiro Quimera')
    expect(screen.getByText(/Comida · por palabra clave/)).toBeTruthy()
    expect(screen.queryByTestId('recordar-regla')).toBeNull() // sin cambiar nada no hay nada que recordar

    fireEvent.change(screen.getByLabelText('Categoría de Zafiro Quimera'), { target: { value: 'Hogar' } })
    const casilla = within(screen.getByTestId('recordar-regla')).getByLabelText(/Recordar para/)
    expect(casilla.checked).toBe(true) // marcado por defecto
    fireEvent.click(screen.getByLabelText('Aplicar también a los anteriores'))
    fireEvent.click(screen.getByRole('button', { name: /Aprobar/ }))
    await waitFor(() =>
      expect(api.aprobarCorreo).toHaveBeenCalledWith('k1', 'bc', { categoria: 'Hogar', recordar: true, aplicar_anteriores: true })
    )
  })

  it('desmarcar «Recordar» aprueba con la categoría pero sin guardar regla', async () => {
    api.correosPendientes.mockResolvedValue([CORREO])
    api.extractosCorreo.mockResolvedValue([])
    montar()
    await screen.findByText('Zafiro Quimera')
    fireEvent.change(screen.getByLabelText('Categoría de Zafiro Quimera'), { target: { value: 'Hogar' } })
    fireEvent.click(within(screen.getByTestId('recordar-regla')).getByLabelText(/Recordar para/))
    fireEvent.click(screen.getByRole('button', { name: /Aprobar/ }))
    await waitFor(() =>
      expect(api.aprobarCorreo).toHaveBeenCalledWith('k1', 'bc', { categoria: 'Hogar', recordar: false, aplicar_anteriores: false })
    )
  })

  it('si quedó en «Otros» le pregunta la categoría', async () => {
    api.correosPendientes.mockResolvedValue([{ ...CORREO, categoria_sugerida: 'Otros', razon_categoria: null, preguntar_categoria: true }])
    api.extractosCorreo.mockResolvedValue([])
    montar()
    await screen.findByText('Zafiro Quimera')
    expect(screen.getByTestId('pregunta-cat-k1')).toBeTruthy()
    expect(screen.getByLabelText('Categoría de Zafiro Quimera').value).toBe('')
    fireEvent.change(screen.getByLabelText('Categoría de Zafiro Quimera'), { target: { value: 'Comida' } })
    expect(screen.queryByTestId('pregunta-cat-k1')).toBeNull()
    expect(screen.getByTestId('recordar-regla')).toBeTruthy()
  })
})
