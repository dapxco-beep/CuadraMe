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


// Una fila de «Todos los extractos» (lo que manda el servidor), con lo mínimo para estas pruebas.
const filaVista = (extra) => ({
  historial_id: null, cuenta_id: null, cuenta: '', copias: 1, copias_texto: '', mes_deducido: false, mes_por_confirmar: false,
  puede_fijar_mes: true, motivo_error: null, tipo: 'cuenta', acciones: [], ...extra,
})
const TODOS = {
  items: [
    filaVista({ id: 'c:e1', extracto_id: 'e1', banco: 'Bancolombia', cuenta_id: 'bc', cuenta: 'Bancolombia Ahorros', mes: '2026-09', mes_etiqueta: 'Septiembre 2026', titulo: 'Bancolombia · Cuenta · Septiembre 2026', estado_vista: 'sin_procesar', estado_etiqueta: 'Sin procesar', resultado: 'Llegó a tu correo y aún no lo hemos leído.', acciones: ['revisar'] }),
    filaVista({ id: 'c:e2', extracto_id: 'e2', banco: 'Nu Colombia', cuenta_id: 'bc', cuenta: 'Bancolombia Ahorros', mes: '2026-08', mes_etiqueta: 'Agosto 2026', titulo: 'Nu Colombia · Cuenta · Agosto 2026', estado_vista: 'revisado', estado_etiqueta: 'Revisado', resultado: 'Leímos 12 movimientos: 12 ya estaban registrados, 0 nuevos.', acciones: ['ver', 'revisar_de_nuevo'] }),
    filaVista({ id: 'c:e3', extracto_id: 'e3', historial_id: 'h9', banco: 'Nequi', mes: '2026-07', mes_etiqueta: 'Julio 2026', titulo: 'Nequi · Cuenta · Julio 2026', estado_vista: 'revisado', estado_etiqueta: 'Revisado', resultado: 'Leímos 1 movimiento: 1 ya estaba registrado, 0 nuevos.', acciones: ['ver'] }),
  ],
  contadores: { revisado: 2, sin_procesar: 1 },
  resumen: '2 revisados · 1 sin procesar',
  sin_adjunto: [],
}

const ESTADO = {
  meses: [], cuentas: [], sin_cuenta: [], ultima_sync: null, todos_extractos: TODOS,
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
import CorreosPorRevisar from '../components/CorreosPorRevisar'

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
    fireEvent.click(await screen.findByTestId('ver-todo')) // los extractos están en «Ver todo»
    expect((await screen.findByTestId('tab-extractos')).textContent).toBe('Extractos · 1')
    expect(screen.getAllByText(/Nuevo · listo para revisar/)).toHaveLength(1)
    // Los ya revisados no salen como nuevos entre los pendientes...
    expect(screen.queryByTestId('extracto-e2')).toBeNull()
    // ...pero SÍ están en «Todos los extractos», con su mes, estado y lo que pasó (no la fila repetida de antes).
    expect(screen.getByTestId('resumen-extractos').textContent).toBe('2 revisados · 1 sin procesar')
    const fila = screen.getByTestId('ext-c:e2')
    expect(within(fila).getByRole('heading', { name: 'Nu Colombia · Cuenta · Agosto 2026' })).toBeTruthy()
    expect(within(fila).getByText('Revisado')).toBeTruthy()
    expect(within(fila).getByText('Leímos 12 movimientos: 12 ya estaban registrados, 0 nuevos.')).toBeTruthy()
    expect(within(screen.getByTestId('ext-c:e3')).getByText('Leímos 1 movimiento: 1 ya estaba registrado, 0 nuevos.')).toBeTruthy()
    expect(screen.queryByText(/coinciden con el banco/)).toBeNull()
  })

  it('«Revisar de nuevo» no bloquea: vuelve a abrir la revisión', async () => {
    api.conciliarExtractoCorreo.mockResolvedValue({ ok: true, historial_id: 'h1' })
    api.obtenerReviewExtracto.mockResolvedValue({ ok: true, historial_id: 'h1', cuenta_id: 'bc', banco_detectado: 'Nu', total_movimientos: 0, review: [] })
    montar()
    fireEvent.click(await screen.findByTestId('ver-todo'))
    fireEvent.click(within(await screen.findByTestId('ext-c:e2')).getByRole('button', { name: /Revisar de nuevo/ }))
    await waitFor(() => expect(api.conciliarExtractoCorreo).toHaveBeenCalledWith('e2', 'bc'))
    expect(await screen.findByTestId('revision-multiple')).toBeTruthy()
  })
})

describe('Correos por revisar: aprender la regla al aprobar', () => {
  // Los movimientos del correo se aprueban en la pantalla Movimientos: aquí se prueban las tarjetas.
  const montarTarjetas = (correos = [CORREO]) =>
    render(<DialogosProvider><CorreosPorRevisar correos={correos} onResuelto={vi.fn()} /></DialogosProvider>)

  it('muestra la razón de la categoría y, si la cambia, deja «Recordar» marcado y lo envía', async () => {
    montarTarjetas()
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
    montarTarjetas()
    await screen.findByText(NOMBRE)
    fireEvent.change(screen.getByLabelText(`Categoría de ${NOMBRE}`), { target: { value: 'Hogar' } })
    fireEvent.click(within(screen.getByTestId('recordar-regla')).getByLabelText(/Recordar para/))
    fireEvent.click(screen.getByRole('button', { name: /^Aprobar$/ }))
    await waitFor(() =>
      expect(api.aprobarCorreo).toHaveBeenCalledWith('k1', 'bc', { categoria: 'Hogar', recordar: false, aplicar_anteriores: false })
    )
  })

  it('si quedó en «Otros» le pregunta la categoría', async () => {
    montarTarjetas([{ ...CORREO, categoria_sugerida: 'Otros', razon_categoria: null, preguntar_categoria: true }])
    await screen.findByText(NOMBRE)
    expect(screen.getByTestId('pregunta-cat-k1')).toBeTruthy()
    expect(screen.getByLabelText(`Categoría de ${NOMBRE}`).value).toBe('')
    fireEvent.change(screen.getByLabelText(`Categoría de ${NOMBRE}`), { target: { value: 'Comida' } })
    expect(screen.queryByTestId('pregunta-cat-k1')).toBeNull()
    expect(screen.getByTestId('recordar-regla')).toBeTruthy()
  })
})
