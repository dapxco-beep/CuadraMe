// Centro Traer movimientos (Sincronización) + cuenta por remitente en los correos por revisar.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [
  { id: 'nu', nombre: 'Nu Colombia', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
  { id: 'bc', nombre: 'Bancolombia Ahorros', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
]

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  guardarClavePdf: vi.fn(),
  conciliarExtractoCorreo: vi.fn(),
  descartarExtractoCorreo: vi.fn(),
  sincronizarCorreos: vi.fn(),
  recategorizarComercio: vi.fn(),
  aprobarCorreo: vi.fn(),
  crearCuenta: vi.fn(),
  obtenerReviewExtracto: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
const recargar = vi.hoisted(() => vi.fn())
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Transporte', 'Otros'], iconoDe: () => '🏷️' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import Sincronizacion from '../screens/Sincronizacion'
import {
  agruparPorBanco, estadoCelda, nombreMes, resumenTareas, textoEstadoExtracto,
} from '../lib/sincronizacion'

const MESES = ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10']
const celda = (mes, estado, extra = {}) => ({ mes, estado, movimientos: 0, conciliados: 0, por_confirmar: 0, extractos: 0, ...extra })

const ESTADO = {
  meses: MESES.map((clave, i) => ({ clave, etiqueta: ['may', 'jun', 'jul', 'ago', 'sep', 'oct'][i] + ' 26' })),
  cuentas: [
    {
      id: 'bc', nombre: 'Bancolombia Ahorros', icono: '🏦',
      meses: [
        celda('2026-05', 'vacio'),
        celda('2026-06', 'conciliado', { movimientos: 18, conciliados: 18, extractos: 1 }),
        celda('2026-07', 'falta_clave', { extractos: 1 }),
        celda('2026-08', 'extracto_pendiente', { extractos: 1 }),
        celda('2026-09', 'sin_extracto', { movimientos: 4, por_confirmar: 1 }),
        celda('2026-10', 'vacio'),
      ],
    },
  ],
  sin_cuenta: [{ banco: 'Nequi', correos: 3, extractos: 0 }],
  tareas: [
    { id: 'falta_clave', titulo: 'Falta la clave del PDF', detalle: 'Guárdala y abro estos extractos por ti.', cantidad: 1, ruta: '/sincronizacion#clave' },
    { id: 'extractos_por_conciliar', titulo: 'Extractos por conciliar', detalle: 'Cruza tu extracto.', cantidad: 2, ruta: '/sincronizacion#extractos' },
    { id: 'sin_cuenta', titulo: 'Bancos sin cuenta', detalle: 'Crea la cuenta de Nequi.', cantidad: 1, ruta: '/sincronizacion#cuentas' },
    { id: 'movimientos_por_categorizar', titulo: 'Movimientos por categorizar', detalle: 'Dime la categoría.', cantidad: 2, ruta: '/sincronizacion#categorizar' },
    { id: 'correos_por_revisar', titulo: 'Correos por revisar', detalle: 'Aprueba o descarta.', cantidad: 3, ruta: '/correos' },
  ],
  ultima_sync: null,
}

const EXTRACTOS = [
  { id: 'e1', banco: 'Bancolombia', periodo: '01/09/2026 a 30/09/2026', asunto: 'x', archivo: 'a.pdf', estado: 'nuevo', cuenta_sugerida_id: 'bc', historial_id: null },
  { id: 'e2', banco: '', periodo: 'agosto 2026', asunto: 'Extracto', archivo: 'b.pdf', estado: 'nuevo', cuenta_sugerida_id: null, historial_id: null },
  { id: 'e3', banco: 'Nequi', periodo: 'julio 2026', asunto: 'x', archivo: 'c.pdf', estado: 'procesado', cuenta_sugerida_id: null, historial_id: 'h9', cruzados: 18 },
  { id: 'e4', banco: 'Davivienda', periodo: 'junio 2026', asunto: 'x', archivo: 'd.pdf', estado: 'falta_clave', cuenta_sugerida_id: null, historial_id: null },
]

const COLA = {
  items: [
    { id: 'm1', descripcion: 'PANADERIA LA 80', categoria: 'Otros', monto: 12000, patron: 'PANADERIA LA 80', cat_confirmada: true },
    { id: 'm2', descripcion: 'Uber trip', categoria: 'Transporte', monto: 8000, patron: 'Uber', cat_confirmada: false },
  ],
  total: 2,
}

function montar(ruta = '/sincronizacion') {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[ruta]}>
        <Routes>
          <Route path="/sincronizacion" element={<Sincronizacion />} />
          <Route path="/conciliacion" element={<p>Pantalla conciliación</p>} />
        </Routes>
      </MemoryRouter>
    </DialogosProvider>
  )
}

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('cuadrame_gmail_sync', String(Date.now())) // recién sincronizado: no hay sincronización automática al abrir
  Object.values(api).forEach((f) => f.mockReset())
  recargar.mockReset()
  api.sincronizacionEstado.mockResolvedValue(ESTADO)
  api.sincronizacionPorCategorizar.mockResolvedValue(COLA)
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', etiqueta: 'gastos' })
  api.extractosCorreo.mockResolvedValue(EXTRACTOS)
  api.clavePdfEstado.mockResolvedValue({ configurada: false })
  api.correosPendientes.mockResolvedValue([])
})

describe('helpers de Sincronización', () => {
  it('resume las tareas en una línea', () => {
    expect(resumenTareas([])).toBe('Todo al día')
    expect(resumenTareas([{}])).toBe('Tienes 1 cosa por resolver')
    expect(resumenTareas([{}, {}, {}, {}])).toBe('Tienes 4 cosas por resolver')
  })

  it('dice el estado de cada extracto en palabras', () => {
    expect(textoEstadoExtracto({ estado: 'procesado', cruzados: 18 })).toBe('Conciliado · 18 movimientos cruzados')
    expect(textoEstadoExtracto({ estado: 'nuevo' })).toBe('Nuevo · listo para revisar')
    expect(textoEstadoExtracto({ estado: 'falta_clave' })).toBe('Falta la clave del PDF')
    expect(textoEstadoExtracto({ estado: 'descartado' })).toBe('Ignorado')
  })

  it('cada estado de celda trae símbolo y texto (el color nunca va solo)', () => {
    expect(estadoCelda('conciliado')).toMatchObject({ simbolo: '✓', texto: 'Conciliado' })
    expect(estadoCelda('extracto_pendiente')).toMatchObject({ simbolo: '⚠', texto: 'Por revisar' })
    expect(estadoCelda('falta_clave')).toMatchObject({ simbolo: '🔑' })
    expect(estadoCelda('sin_extracto')).toMatchObject({ simbolo: '—' })
    expect(estadoCelda('raro').texto).toBe('Sin datos')
  })

  it('agrupa por banco y deja "Banco sin identificar" al final', () => {
    const g = agruparPorBanco([{ banco: '' }, { banco: 'Nequi' }, { banco: 'Nequi' }, { banco: 'Bancolombia' }])
    expect(g.map((x) => [x.banco, x.items.length])).toEqual([['Nequi', 2], ['Bancolombia', 1], ['Banco sin identificar', 1]])
    expect(nombreMes('2026-06')).toBe('junio 2026')
  })
})

describe('pantalla Sincronización', () => {
  it('muestra el resumen, las tareas en orden y quita las que ya no hay', async () => {
    montar()
    expect(await screen.findByText('Tienes 5 cosas por resolver')).toBeTruthy()
    const tarjetas = screen.getAllByTestId(/^tarea-/).map((t) => t.getAttribute('data-testid'))
    expect(tarjetas).toEqual(['tarea-falta_clave', 'tarea-extractos_por_conciliar', 'tarea-sin_cuenta', 'tarea-movimientos_por_categorizar', 'tarea-correos_por_revisar'])
    expect(screen.queryByTestId('tarea-movimientos_por_confirmar')).toBeNull()
    expect(screen.getByRole('button', { name: 'Traer todo ahora' })).toBeTruthy()
  })

  it('sin tareas muestra "Todo al día" con la fecha de la última vez', async () => {
    api.sincronizacionEstado.mockResolvedValue({ ...ESTADO, tareas: [], sin_cuenta: [], ultima_sync: new Date(Date.now() - 2 * 3600 * 1000).toISOString().replace('Z', '') })
    montar()
    const vacio = await screen.findByTestId('todo-al-dia')
    expect(vacio.textContent).toMatch(/Todo al día · última vez hace 2 h/)
    expect(screen.getByTestId('resumen-tareas').textContent).toBe('Todo al día')
    // Cada bloque con cero pendientes queda en «Todo al día».
    expect(screen.getByTestId('al-dia-sinc-correo')).toBeTruthy()
    expect(screen.getByTestId('al-dia-sinc-revisar')).toBeTruthy()
  })

  it('la grilla tiene texto accesible por celda y al tocarla abre el detalle del mes', async () => {
    montar()
    await screen.findByText('Tienes 5 cosas por resolver')
    expect(screen.getByRole('button', { name: 'Bancolombia Ahorros, junio 2026: Conciliado' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Bancolombia Ahorros, julio 2026: Falta la clave' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Bancolombia Ahorros, agosto 2026: Por revisar' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Bancolombia Ahorros, septiembre 2026: Sin extracto' }))
    const det = screen.getByRole('region', { name: 'Detalle del mes' })
    expect(within(det).getByText(/4 movimientos · 0 conciliados · 1 por confirmar/)).toBeTruthy()
    expect(within(det).getByRole('button', { name: 'Buscar extracto' })).toBeTruthy()
  })

  it('"Crear cuenta Nequi" abre el selector con Nequi ya elegido y crea la cuenta', async () => {
    api.crearCuenta.mockResolvedValue({ id: 'nq', nombre: 'Nequi' })
    montar()
    await screen.findByText('Tienes 5 cosas por resolver')
    fireEvent.click(screen.getAllByRole('button', { name: 'Crear cuenta Nequi' })[0])
    const hoja = screen.getByRole('dialog', { name: 'Crear cuenta Nequi' })
    expect(within(hoja).getByRole('button', { name: /Nequi/, pressed: true })).toBeTruthy()
    fireEvent.click(within(hoja).getByRole('button', { name: 'Crear cuenta' }))
    await waitFor(() => expect(api.crearCuenta).toHaveBeenCalledWith(expect.objectContaining({ nombre: 'Nequi', tipo: 'ahorro' })))
    await waitFor(() => expect(recargar).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('los extractos dicen banco, estado en palabras y no se concilian sin cuenta elegida', async () => {
    api.conciliarExtractoCorreo.mockResolvedValue({ ok: true, historial_id: 'h1' })
    montar()
    await screen.findByText('Tienes 5 cosas por resolver')
    const nuevo = screen.getByTestId('extracto-e1')
    expect(within(nuevo).getByText('Nuevo · listo para revisar')).toBeTruthy()
    expect(within(nuevo).getByText('Cuenta: Bancolombia Ahorros')).toBeTruthy()
    // Lo ya conciliado no es pendiente: va en una sección plegada 'Extractos ya revisados (N)'.
    expect(screen.queryByText('Conciliado · 18 movimientos cruzados')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Extractos ya revisados \(1\)/ }))
    expect(screen.getByText(/18 movimientos cruzados/)).toBeTruthy()
    expect(within(screen.getByTestId('extracto-e4')).getByText('Falta la clave del PDF')).toBeTruthy()

    // Sin banco detectado: se dice, y la cuenta es obligatoria.
    const sinBanco = screen.getByTestId('extracto-e2')
    expect(within(sinBanco).getByText(/Banco sin identificar/)).toBeTruthy()
    const boton = within(sinBanco).getByRole('button', { name: 'Revisar extracto' })
    expect(boton.disabled).toBe(true)
    fireEvent.change(within(sinBanco).getByLabelText(/Cuenta del extracto/), { target: { value: 'nu' } })
    expect(boton.disabled).toBe(false)

    // El del banco conocido usa la sugerida y abre la revisión AQUÍ MISMO (sin cambiar de pantalla).
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h1', cuenta_id: 'bc', banco_detectado: 'Bancolombia', total_movimientos: 1, descartados: 0,
      review: [{ fingerprint: 'f1', fecha: '2026-09-02', descripcion: 'Compra D1', monto: 1000, tipo: 'expense', estado: 'faltante' }],
    })
    fireEvent.click(within(nuevo).getByRole('button', { name: 'Revisar extracto' }))
    await waitFor(() => expect(api.conciliarExtractoCorreo).toHaveBeenCalledWith('e1', 'bc'))
    expect(await screen.findByTestId('revision-multiple')).toBeTruthy()
    expect(api.obtenerReviewExtracto).toHaveBeenCalledWith('h1')
  })

  it('por categorizar: elegir categoría recuerda el comercio por defecto; la casilla lo evita', async () => {
    api.recategorizarComercio.mockResolvedValue({ ok: true, actualizados: 3, patron: 'PANADERIA LA 80' })
    montar()
    await screen.findByTestId('cat-m1')
    const m1 = screen.getByTestId('cat-m1')
    const casilla = within(m1).getByRole('checkbox')
    expect(casilla.checked).toBe(true)
    fireEvent.change(within(m1).getByLabelText('Categoría de PANADERIA LA 80'), { target: { value: 'Comida' } })
    await waitFor(() => expect(api.recategorizarComercio).toHaveBeenCalledWith('m1', { categoria: 'Comida', aplicar_a_todos: true, patron: 'PANADERIA LA 80' }))

    const m2 = screen.getByTestId('cat-m2')
    fireEvent.click(within(m2).getByRole('checkbox'))
    fireEvent.change(within(m2).getByLabelText('Categoría de Uber trip'), { target: { value: 'Transporte' } })
    await waitFor(() => expect(api.recategorizarComercio).toHaveBeenCalledWith('m2', { categoria: 'Transporte', aplicar_a_todos: false, patron: 'Uber' }))
  })

  it('Traer todo ahora lee Gmail por lotes con progreso y resume lo nuevo', async () => {
    let terminar
    const segundo = new Promise((res) => { terminar = res })
    api.sincronizarCorreos
      .mockResolvedValueOnce({ ok: true, completado: false, leidos: 120, total_estimado: 340 })
      .mockReturnValueOnce(segundo)
    montar()
    await screen.findByText('Tienes 5 cosas por resolver')
    fireEvent.click(screen.getByRole('button', { name: 'Traer todo ahora' }))
    expect(await screen.findByText('Leí 120 de 340')).toBeTruthy()
    terminar({ ok: true, completado: true, leidos: 340, total_estimado: 340, nuevos: 12, extractos_nuevos: 2, extractos_encontrados: 2 })
    expect(await screen.findByText(/Leí 340 correos\. Encontré 12 movimientos nuevos y 2 extractos\./)).toBeTruthy()
    expect(api.sincronizarCorreos).toHaveBeenCalledTimes(2)
    // Al terminar vuelve a pedir el estado para refrescar tareas y grilla.
    await waitFor(() => expect(api.sincronizacionEstado.mock.calls.length).toBeGreaterThanOrEqual(2))
  })

  it('muestra el error de carga con Reintentar', async () => {
    api.sincronizacionEstado.mockRejectedValueOnce(new Error('Sin conexión'))
    montar()
    expect(await screen.findByText('Sin conexión')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Tienes 5 cosas por resolver')).toBeTruthy()
  })
})

describe('Correos por revisar: la cuenta sale de quién envió el correo', () => {
  const NEQUI = { id: 'k1', comercio: 'Bre-B', asunto: '¡Enviaste plata por Bre-B!', categoria_sugerida: 'Otros', tipo_sugerido: 'expense', monto: 500, banco_detectado: 'Nequi', cuenta_sugerida_id: null, falta_cuenta: true }
  const BANCO = { id: 'k2', comercio: 'Exito', asunto: 'Compra', categoria_sugerida: 'Mercado', tipo_sugerido: 'expense', monto: 45000, banco_detectado: 'Bancolombia', cuenta_sugerida_id: 'bc', falta_cuenta: false }
  const RARO = { id: 'k3', comercio: 'Tienda', asunto: 'Pago', categoria_sugerida: 'Otros', tipo_sugerido: 'expense', monto: 9000, banco_detectado: null, cuenta_sugerida_id: null, falta_cuenta: false }

  beforeEach(() => {
    api.extractosCorreo.mockResolvedValue([])
    api.correosPendientes.mockResolvedValue([NEQUI, BANCO, RARO])
    localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
  })

  it('nunca preselecciona la primera cuenta: un correo de Nequi sin cuenta Nequi no se puede aprobar', async () => {
    montar()
    await screen.findByText('Bre-B')
    const selector = screen.getByLabelText('Cuenta de Bre-B')
    expect(selector.value).toBe('') // antes caía en "Nu Colombia" (cuentas[0])
    expect(within(selector).getByText('No tienes cuenta Nequi')).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'Crear cuenta Nequi' }).length).toBeGreaterThan(0)
    const aprobar = screen.getAllByRole('button', { name: /Aprobar/ })
    expect(aprobar[0].disabled).toBe(true)
  })

  it('usa la cuenta sugerida por el servidor y aprueba con ella', async () => {
    api.aprobarCorreo.mockResolvedValue({})
    montar()
    await screen.findByText('Exito')
    expect(screen.getByLabelText('Cuenta de Exito').value).toBe('bc')
    const aprobar = screen.getAllByRole('button', { name: /Aprobar/ })
    expect(aprobar[1].disabled).toBe(false)
    fireEvent.click(aprobar[1])
    await waitFor(() => expect(api.aprobarCorreo).toHaveBeenCalledWith('k2', 'bc'))
  })

  it('sin banco detectado exige elegir la cuenta a mano', async () => {
    api.aprobarCorreo.mockResolvedValue({})
    montar()
    await screen.findByText('Tienda')
    const selector = screen.getByLabelText('Cuenta de Tienda')
    const aprobar = screen.getAllByRole('button', { name: /Aprobar/ })[2]
    expect(selector.value).toBe('')
    expect(aprobar.disabled).toBe(true)
    fireEvent.change(selector, { target: { value: 'nu' } })
    expect(aprobar.disabled).toBe(false)
    fireEvent.click(aprobar)
    await waitFor(() => expect(api.aprobarCorreo).toHaveBeenCalledWith('k3', 'nu'))
  })
})
