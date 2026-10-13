// Centro Traer movimientos: lo ya conciliado no es pendiente (sección plegada) y al aprobar un
// correo con otra categoría se recuerda la regla del comercio.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [{ id: 'bc', nombre: 'Bancolombia Ahorros', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]

const EXTRACTOS = [
  { id: 'e1', banco: 'Bancolombia', periodo: 'octubre 2026', asunto: 'Extracto', archivo: 'a.pdf', estado: 'nuevo', cuenta_sugerida_id: 'bc', historial_id: null },
  { id: 'e2', banco: 'Nu Colombia', periodo: 'septiembre 2026', asunto: 'Extracto', archivo: 'b.pdf', estado: 'ya_conciliado', cuenta_sugerida_id: 'bc', historial_id: null, cruzados: 12 },
  { id: 'e3', banco: 'Nequi', periodo: 'agosto 2026', asunto: 'Extracto', archivo: 'c.pdf', estado: 'procesado', cuenta_sugerida_id: null, historial_id: 'h9', cruzados: 1 },
]

const ESTADO = {
  meses: [], cuentas: [], sin_cuenta: [], ultima_sync: null,
  tareas: [{ id: 'extractos_por_conciliar', titulo: 'Extractos por conciliar', detalle: '', cantidad: 1, ruta: '/sincronizacion#extractos' }],
}
const ESTADO_CORREO = {
  ...ESTADO,
  tareas: [{ id: 'correos_por_revisar', titulo: 'Correos por revisar', detalle: '', cantidad: 1, ruta: '/sincronizacion#correos' }],
}

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  aprobarCorreo: vi.fn(),
  conciliarExtractoCorreo: vi.fn(),
  sincronizarCorreos: vi.fn(),
  obtenerReviewExtracto: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Hogar', 'Otros'], iconoDe: () => '' }),
}))

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

const CORREO = {
  id: 'k1', comercio: 'Compra en Zafiro Quimera', asunto: 'Compra aprobada', categoria_sugerida: 'Comida', tipo_sugerido: 'expense',
  monto: 15000, banco_detectado: 'Bancolombia', cuenta_sugerida_id: 'bc', falta_cuenta: false,
  razon_categoria: 'por palabra clave «zafiro»', preguntar_categoria: false,
}
const NOMBRE = 'Compra en Zafiro Quimera'

beforeEach(() => {
  localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
  Object.values(api).forEach((f) => f.mockReset())
  api.sincronizacionEstado.mockResolvedValue(ESTADO)
  api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', etiqueta: 'gastos' })
  api.correosPendientes.mockResolvedValue([])
  api.extractosCorreo.mockResolvedValue(EXTRACTOS)
  api.clavePdfEstado.mockResolvedValue({ configurada: false })
  api.aprobarCorreo.mockResolvedValue({})
})

describe('Extractos ya conciliados', () => {
  it('no cuentan ni aparecen como nuevos: quedan en una sección plegada con sus movimientos cruzados', async () => {
    montar()
    expect((await screen.findByRole('heading', { level: 3, name: /Extractos para conciliar/ })).textContent).toBe('Extractos para conciliar1')
    expect(screen.getAllByText(/Nuevo · listo para revisar/)).toHaveLength(1)
    expect(screen.queryByText('Nu Colombia')).toBeNull()

    const boton = screen.getByRole('button', { name: /Extractos ya revisados \(2\)/ })
    expect(boton.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(boton)
    const fila = screen.getByTestId('conciliado-e2')
    expect(within(fila).getByText(/Nu Colombia · septiembre 2026/)).toBeTruthy()
    expect(within(fila).getByText(/Bancolombia Ahorros · 12 movimientos coinciden con el banco/)).toBeTruthy()
    expect(within(screen.getByTestId('conciliado-e3')).getByText('1 movimiento coincide con el banco')).toBeTruthy()
  })

  it('«Revisar de nuevo» no bloquea: vuelve a abrir la revisión', async () => {
    api.conciliarExtractoCorreo.mockResolvedValue({ ok: true, historial_id: 'h1' })
    api.obtenerReviewExtracto.mockResolvedValue({ ok: true, historial_id: 'h1', cuenta_id: 'bc', banco_detectado: 'Nu', total_movimientos: 0, review: [] })
    montar()
    await screen.findByRole('heading', { level: 3, name: /Extractos para conciliar/ })
    fireEvent.click(screen.getByRole('button', { name: /Extractos ya revisados \(2\)/ }))
    fireEvent.click(within(screen.getByTestId('conciliado-e2')).getByRole('button', { name: 'Revisar de nuevo' }))
    await waitFor(() => expect(api.conciliarExtractoCorreo).toHaveBeenCalledWith('e2', 'bc'))
    expect(await screen.findByTestId('revision-multiple')).toBeTruthy()
  })
})

describe('Correos por revisar: aprender la regla al aprobar', () => {
  beforeEach(() => {
    api.sincronizacionEstado.mockResolvedValue(ESTADO_CORREO)
    api.correosPendientes.mockResolvedValue([CORREO])
    api.extractosCorreo.mockResolvedValue([])
  })

  it('muestra la razón de la categoría y, si la cambia, deja «Recordar» marcado y lo envía', async () => {
    montar()
    await screen.findByText(NOMBRE)
    expect(screen.getByText(/Comida · por palabra clave/)).toBeTruthy()
    expect(screen.queryByTestId('recordar-regla')).toBeNull() // sin cambiar nada no hay nada que recordar

    fireEvent.change(screen.getByLabelText(`Categoría de ${NOMBRE}`), { target: { value: 'Hogar' } })
    const casilla = within(screen.getByTestId('recordar-regla')).getByLabelText(/Recordar para/)
    expect(casilla.checked).toBe(true) // marcado por defecto
    fireEvent.click(screen.getByLabelText('Aplicar también a los anteriores'))
    fireEvent.click(screen.getByRole('button', { name: /^Aprobar$/ }))
    await waitFor(() =>
      expect(api.aprobarCorreo).toHaveBeenCalledWith('k1', 'bc', { categoria: 'Hogar', recordar: true, aplicar_anteriores: true })
    )
  })

  it('desmarcar «Recordar» aprueba con la categoría pero sin guardar regla', async () => {
    montar()
    await screen.findByText(NOMBRE)
    fireEvent.change(screen.getByLabelText(`Categoría de ${NOMBRE}`), { target: { value: 'Hogar' } })
    fireEvent.click(within(screen.getByTestId('recordar-regla')).getByLabelText(/Recordar para/))
    fireEvent.click(screen.getByRole('button', { name: /^Aprobar$/ }))
    await waitFor(() =>
      expect(api.aprobarCorreo).toHaveBeenCalledWith('k1', 'bc', { categoria: 'Hogar', recordar: false, aplicar_anteriores: false })
    )
  })

  it('si quedó en «Otros» le pregunta la categoría', async () => {
    api.correosPendientes.mockResolvedValue([{ ...CORREO, categoria_sugerida: 'Otros', razon_categoria: null, preguntar_categoria: true }])
    montar()
    await screen.findByText(NOMBRE)
    expect(screen.getByTestId('pregunta-cat-k1')).toBeTruthy()
    expect(screen.getByLabelText(`Categoría de ${NOMBRE}`).value).toBe('')
    fireEvent.change(screen.getByLabelText(`Categoría de ${NOMBRE}`), { target: { value: 'Comida' } })
    expect(screen.queryByTestId('pregunta-cat-k1')).toBeNull()
    expect(screen.getByTestId('recordar-regla')).toBeTruthy()
  })
})
