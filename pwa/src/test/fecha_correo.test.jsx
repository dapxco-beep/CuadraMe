// Los movimientos del correo viven en Movimientos («Por revisar · N del correo») con su fecha visible,
// editable y agrupada por día; Traer movimientos solo manda a verlos.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const MOVS = [
  { id: 'm1', cuenta_id: 'c1', fecha: '2026-10-04T12:00:00', descripcion: 'Netflix', categoria: 'Ocio', tipo: 'expense', monto: 30000, fuente: 'manual', notas: '', cat_origen: null, cat_confirmada: true },
]
const CORREOS = [
  {
    id: 'k1', comercio: 'Envío a Ana', asunto: 'Enviaste 45.500', categoria_sugerida: 'Otros', tipo_sugerido: 'expense', monto: 45500,
    banco_detectado: 'Nequi', cuenta_sugerida_id: 'c2', falta_cuenta: false, preguntar_categoria: false,
    fecha_movimiento: '2026-10-03T11:05:00', fecha_movimiento_con_hora: true, fecha_del_texto: true, recibido_en_co: '2026-10-08T21:30:00',
  },
  {
    id: 'k2', comercio: 'Compra en Rappi', asunto: 'Pagaste en Rappi con Cuenta Nu', categoria_sugerida: 'Comida', tipo_sugerido: 'expense', monto: 18000,
    banco_detectado: 'Nu Colombia', cuenta_sugerida_id: 'c2', falta_cuenta: false, preguntar_categoria: false,
    fecha_movimiento: '2026-10-08T21:30:00', fecha_movimiento_con_hora: true, fecha_del_texto: false, recibido_en_co: '2026-10-08T21:30:00',
  },
]

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => {
  const cuentas = [
    { id: 'c1', nombre: 'Principal', saldo: 1, moneda: 'COP', tipo: 'ahorro' },
    { id: 'c2', nombre: 'Nequi', saldo: 1, moneda: 'COP', tipo: 'ahorro' },
  ]
  const valor = { cuentas, cargando: false, error: '', recargar: () => Promise.resolve() }
  return { useCuentas: () => valor }
})
vi.mock('../lib/CategoriasContext', () => {
  const valor = {
    categorias: [], activas: [], nombres: ['Comida', 'Otros'], cargando: false, recargar: () => Promise.resolve(),
    iconoDe: (n) => (n === 'Comida' ? '🍔' : '📦'), colorDe: () => null,
  }
  return { useCategorias: () => valor }
})

import { DialogosProvider } from '../lib/DialogosContext'
import Movimientos from '../screens/Movimientos'
import { vaciarCachesListas } from '../lib/useEstadoLista'
import {
  agruparPorDia, etiquetaDia, etiquetaFechaHora, fechaParaEnviar, fechasDistintas, partesFecha,
} from '../lib/fechaCorreo'

function montar(ruta = '/movimientos') {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[ruta]}>
        <Routes><Route path="/movimientos" element={<Movimientos />} /></Routes>
      </MemoryRouter>
    </DialogosProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vaciarCachesListas()
  window.sessionStorage.clear()
  Object.assign(api, {
    movimientos: vi.fn().mockResolvedValue(MOVS),
    conteoPorRevisar: vi.fn().mockResolvedValue({ auto: 0, otros: 0, total: 0 }),
    correosPendientes: vi.fn().mockResolvedValue(CORREOS),
    aprobarCorreo: vi.fn().mockResolvedValue({}),
    descartarCorreo: vi.fn().mockResolvedValue({}),
  })
})

describe('lib/fechaCorreo', () => {
  it('lee la fecha por partes y la dice en palabras', () => {
    expect(partesFecha('2026-10-08T16:30:00')).toEqual({ a: 2026, m: 10, d: 8, h: 16, mi: 30 })
    expect(etiquetaFechaHora('2026-10-08T16:30:00')).toBe('Jue 8 oct 2026 · 4:30 pm')
    expect(etiquetaFechaHora('2026-10-08T00:05:00')).toBe('Jue 8 oct 2026 · 12:05 am')
    expect(etiquetaFechaHora('2026-10-08T00:00:00', false)).toBe('Jue 8 oct 2026')
    expect(partesFecha('basura')).toBeNull()
  })

  it('encabezados por día: Hoy, Ayer y la fecha', () => {
    const hoy = new Date(2026, 9, 12)
    expect(etiquetaDia('2026-10-12T08:00:00', hoy)).toBe('Hoy')
    expect(etiquetaDia('2026-10-11T23:00:00', hoy)).toBe('Ayer')
    expect(etiquetaDia('2026-10-08T09:00:00', hoy)).toBe('8 oct')
    expect(etiquetaDia('2025-12-31T09:00:00', hoy)).toBe('31 dic 2025')
    const g = agruparPorDia([{ fecha_movimiento: '2026-10-12T10:00:00' }, { fecha_movimiento: '2026-10-12T09:00:00' }, { fecha_movimiento: '2026-10-08T09:00:00' }], hoy)
    expect(g.map((x) => [x.etiqueta, x.items.length])).toEqual([['Hoy', 2], ['8 oct', 1]])
  })

  it('al editar el día se conserva la hora, y avisa cuando la llegada difiere', () => {
    expect(fechaParaEnviar('2026-10-06', '2026-10-03T11:05:00')).toBe('2026-10-06T11:05:00')
    expect(fechasDistintas('2026-10-03T11:05:00', '2026-10-08T21:30:00')).toBe(true)
    expect(fechasDistintas('2026-10-08T21:29:00', '2026-10-08T21:30:00')).toBe(false)
  })
})

describe('Movimientos: «Por revisar · N del correo»', () => {
  it('muestra la sección arriba de la lista con la fecha y hora de cada movimiento, y ambas fechas si difieren', async () => {
    montar()
    const seccion = await screen.findByTestId('por-revisar-correo')
    expect(within(seccion).getByRole('heading', { level: 2 })).toHaveTextContent('Por revisar · 2 del correo')
    // el movimiento que difiere del correo muestra la fecha del movimiento y cuándo llegó el correo
    const k1 = within(seccion).getByTestId('fecha-k1')
    expect(k1).toHaveTextContent('Sáb 3 oct 2026 · 11:05 am')
    expect(k1).toHaveTextContent('Fecha del movimiento (la que usaré)')
    expect(k1).toHaveTextContent('Llegó el correo el Jue 8 oct 2026 · 9:30 pm')
    // el aviso sin fecha usa la de recepción y no repite
    expect(within(seccion).getByTestId('fecha-k2')).not.toHaveTextContent('Llegó el correo')
    // encabezados por día, el más reciente primero (orden que manda el servidor)
    expect(seccion.querySelectorAll('h4')[0]).toHaveTextContent('8 oct')
    expect(await screen.findByText('Netflix')).toBeTruthy() // la lista normal sigue debajo
  })

  it('aprobar sin tocar nada no manda fecha; con la fecha editada la manda y el movimiento sale de la sección', async () => {
    montar()
    const seccion = await screen.findByTestId('por-revisar-correo')
    const tarjeta = within(seccion).getByTestId('correo-k1')
    fireEvent.click(within(tarjeta).getByRole('button', { name: /Editar/ }))
    fireEvent.change(within(tarjeta).getByLabelText('Fecha de Envío a Ana'), { target: { value: '2026-10-05' } })
    expect(within(tarjeta).getByTestId('fecha-k1')).toHaveTextContent('Lun 5 oct 2026 · 11:05 am')
    fireEvent.click(within(tarjeta).getByRole('button', { name: /^Aprobar$/ }))
    await waitFor(() => expect(api.aprobarCorreo).toHaveBeenCalledWith('k1', 'c2', { fecha: '2026-10-05T11:05:00' }))
    await waitFor(() => expect(screen.queryByTestId('correo-k1')).toBeNull())
    expect(screen.getByTestId('correo-k2')).toBeTruthy()
    expect(api.movimientos.mock.calls.length).toBeGreaterThan(1) // la lista se volvió a pedir sin recargar la pantalla
  })

  it('el chip «Del correo por revisar» deja solo la sección; «Descartar» la vacía', async () => {
    montar('/movimientos?filtro=por-revisar')
    expect(await screen.findByTestId('por-revisar-correo')).toBeTruthy()
    expect(screen.queryByText('Netflix')).toBeNull()
    expect(screen.getByRole('button', { name: /Del correo por revisar \(2\)/ })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(within(screen.getByTestId('correo-k2')).getByRole('button', { name: /Descartar/ }))
    await waitFor(() => expect(api.descartarCorreo).toHaveBeenCalledWith('k2'))
  })

  it('sin correos pendientes no hay sección ni chip', async () => {
    api.correosPendientes.mockResolvedValue([])
    montar()
    await screen.findByText('Netflix')
    expect(screen.queryByTestId('por-revisar-correo')).toBeNull()
    expect(screen.queryByRole('button', { name: /Del correo por revisar/ })).toBeNull()
  })
})
