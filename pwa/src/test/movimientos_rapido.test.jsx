import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { Link, MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

const MOVS = [
  { id: 'm1', cuenta_id: 'c1', fecha: '2026-10-04T12:00:00', descripcion: 'Compra PANADERIA LA 80 0105', categoria: 'Otros', tipo: 'expense', monto: 12000, fuente: 'manual', notas: '', cat_origen: null, cat_confirmada: true },
  { id: 'm2', cuenta_id: 'c1', fecha: '2026-10-03T12:00:00', descripcion: 'PANADERIA LA 80 BOGOTA', categoria: 'Otros', tipo: 'expense', monto: 8000, fuente: 'manual', notas: '', cat_origen: null, cat_confirmada: true },
  { id: 'm3', cuenta_id: 'c1', fecha: '2026-10-02T12:00:00', descripcion: 'Pago panaderia la 80', categoria: 'Otros', tipo: 'expense', monto: 5000, fuente: 'manual', notas: '', cat_origen: null, cat_confirmada: true },
  { id: 'm4', cuenta_id: 'c2', fecha: '2026-10-01T12:00:00', descripcion: 'Netflix', categoria: 'Ocio', tipo: 'expense', monto: 30000, fuente: 'manual', notas: '', cat_origen: null, cat_confirmada: true },
]
const { CATS, ICONOS } = vi.hoisted(() => ({
  CATS: ['Comida', 'Ocio', 'Hogar', 'Otros'],
  ICONOS: { Comida: '🍔', Ocio: '🎬', Hogar: '🏠', Otros: '📦' },
}))

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
    categorias: [], activas: [], nombres: CATS, cargando: false, recargar: () => Promise.resolve(),
    iconoDe: (n) => ICONOS[n] || '💳', colorDe: () => null,
  }
  return { useCategorias: () => valor }
})

import { DialogosProvider } from '../lib/DialogosContext'
import Movimientos from '../screens/Movimientos'
import { vaciarCachesListas } from '../lib/useEstadoLista'
import { agruparPorComercio, consultaServidor, leerFiltros } from '../lib/movimientosLista'

function Donde() {
  const l = useLocation()
  return <p data-testid="donde">{l.pathname + l.search}</p>
}

function Detalle() {
  const navigate = useNavigate()
  return <button onClick={() => navigate(-1)}>Volver al listado</button>
}

function montar(ruta = '/movimientos') {
  return render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[ruta]}>
        <Routes>
          <Route path="/movimientos" element={<Movimientos />} />
          <Route path="/movimientos/:id" element={<Detalle />} />
        </Routes>
        <Donde />
      </MemoryRouter>
    </DialogosProvider>
  )
}

// jsdom no hace layout: scrollTop se simula con un valor por elemento
const scrolls = new WeakMap()
Object.defineProperty(HTMLElement.prototype, 'scrollTop', {
  configurable: true,
  get() {
    return scrolls.get(this) ?? 0
  },
  set(v) {
    scrolls.set(this, v)
  },
})

beforeEach(() => {
  vi.clearAllMocks()
  vaciarCachesListas()
  window.sessionStorage.clear()
  Object.assign(api, {
    movimientos: vi.fn().mockResolvedValue(MOVS),
    conteoPorRevisar: vi.fn().mockResolvedValue({ auto: 0, otros: 3, total: 3 }),
    recategorizarMasivo: vi.fn().mockResolvedValue({ ok: true, actualizados: 1 }),
    aprenderRegla: vi.fn().mockResolvedValue({ guardada: true, actualizada: false, huella: 'panaderia', anteriores_actualizados: 0 }),
    similaresConteo: vi.fn().mockResolvedValue({ huella: 'panaderia', conteo: 3 }),
    reglasCategoria: vi.fn().mockResolvedValue([{ id: 'r1', patron: 'panaderia', categoria: 'Comida' }]),
    eliminarReglaCategoria: vi.fn().mockResolvedValue({ ok: true }),
    eliminarMovimientosMasivo: vi.fn().mockResolvedValue({ ok: true, actualizados: 4, omitidos: 0 }),
    moverMovimientosMasivo: vi.fn().mockResolvedValue({ ok: true, actualizados: 1, omitidos: 0 }),
    confirmarCategorias: vi.fn().mockResolvedValue({ ok: true }),
  })
})

const chipDe = (desc) => screen.getByRole('button', { name: `Cambiar categoría de ${desc}` })

describe('categorizar sin abrir el movimiento', () => {
  it('el chip guarda al elegir, sin navegar, y Deshacer lo revierte', async () => {
    montar()
    await screen.findByText('Netflix')
    await userEvent.click(chipDe('Compra PANADERIA LA 80 0105'))
    const hoja = await screen.findByRole('dialog')
    // «Recordar para este comercio» es opcional: viene activada solo porque se repite (3 más + este = 4)
    // y muestra cuántos más hay del mismo comercio
    await waitFor(() => expect(within(hoja).getByRole('checkbox', { name: /Recordar para este comercio/ })).toBeChecked())
    expect(await within(hoja).findByText('3 movimientos más')).toBeInTheDocument()
    await userEvent.click(within(hoja).getByRole('button', { name: /Comida/ }))

    await waitFor(() => expect(api.recategorizarMasivo).toHaveBeenCalledWith(['m1'], 'Comida'))
    expect(api.aprenderRegla).toHaveBeenCalledWith({
      descripcion: 'Compra PANADERIA LA 80 0105', categoria: 'Comida', aplicar_anteriores: false,
    })
    // actualización optimista: el chip ya dice Comida y seguimos en la lista (no se abrió el detalle)
    expect(chipDe('Compra PANADERIA LA 80 0105')).toHaveTextContent('Comida')
    expect(screen.getByTestId('donde')).toHaveTextContent('/movimientos')
    expect(api.movimientos).toHaveBeenCalledTimes(1) // sin recargar la lista

    await userEvent.click(await screen.findByRole('button', { name: 'Deshacer' }))
    await waitFor(() => expect(api.recategorizarMasivo).toHaveBeenLastCalledWith(['m1'], 'Otros'))
    await waitFor(() => expect(api.eliminarReglaCategoria).toHaveBeenCalledWith('r1')) // la regla recién creada se quita
    expect(chipDe('Compra PANADERIA LA 80 0105')).toHaveTextContent('Otros')
  })

  it('"Aplicar a los anteriores" pide aplicar_anteriores y cambia los ya cargados del mismo comercio', async () => {
    api.aprenderRegla.mockResolvedValue({ guardada: true, actualizada: false, huella: 'panaderia', anteriores_actualizados: 2 })
    montar()
    await screen.findByText('Netflix')
    await userEvent.click(chipDe('Compra PANADERIA LA 80 0105'))
    const hoja = await screen.findByRole('dialog')
    await userEvent.click(await within(hoja).findByRole('checkbox', { name: /Aplicar a los anteriores/ }))
    await userEvent.click(within(hoja).getByRole('button', { name: /Comida/ }))
    await waitFor(() =>
      expect(api.aprenderRegla).toHaveBeenCalledWith(expect.objectContaining({ aplicar_anteriores: true }))
    )
    expect(chipDe('PANADERIA LA 80 BOGOTA')).toHaveTextContent('Comida')
    expect(chipDe('Pago panaderia la 80')).toHaveTextContent('Comida')
    expect(chipDe('Netflix')).toHaveTextContent('Ocio')
  })

  it('con "Sin categorizar" activo pasa solo al siguiente movimiento', async () => {
    montar('/movimientos?cat=Otros')
    await screen.findByText('PANADERIA LA 80 BOGOTA')
    await userEvent.click(chipDe('Compra PANADERIA LA 80 0105'))
    const hoja = await screen.findByRole('dialog')
    await userEvent.click(within(hoja).getByRole('button', { name: /Comida/ }))
    // el categorizado sale del filtro y se abre el selector del siguiente
    await waitFor(() => expect(screen.queryByText('Compra PANADERIA LA 80 0105')).toBeNull())
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveTextContent('PANADERIA LA 80 BOGOTA'), { timeout: 3000 })
  })
})

describe('selección múltiple y edición masiva', () => {
  it('casilla -> modo selección; todo lo filtrado; eliminar pide confirmación', async () => {
    montar()
    await screen.findByText('Netflix')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Seleccionar Netflix' }))
    expect(screen.getByText('1 seleccionado')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Seleccionar todo lo filtrado \(4\)/ }))
    expect(screen.getByText('4 seleccionados')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Eliminar/ }))
    const dialogo = await screen.findByRole('alertdialog')
    expect(dialogo).toHaveTextContent('¿Eliminar 4 movimientos?')
    expect(api.eliminarMovimientosMasivo).not.toHaveBeenCalled() // solo tras confirmar
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Eliminar' }))
    await waitFor(() => expect(api.eliminarMovimientosMasivo).toHaveBeenCalledWith(['m1', 'm2', 'm3', 'm4']))
    await waitFor(() => expect(screen.queryByText('Netflix')).toBeNull())
  })

  it('"Seleccionar los similares" marca los del mismo comercio y Categoría los mueve juntos', async () => {
    montar()
    await screen.findByText('Netflix')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Seleccionar PANADERIA LA 80 BOGOTA' }))
    await userEvent.click(screen.getByRole('button', { name: 'Seleccionar los similares' }))
    expect(screen.getByText('3 seleccionados')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Categoría' }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: /Hogar/ }))
    await waitFor(() => expect(api.recategorizarMasivo).toHaveBeenCalledWith(['m1', 'm2', 'm3'], 'Hogar'))
    expect(api.aprenderRegla).not.toHaveBeenCalled() // en masivo no se crean reglas
  })

  it('"Cuenta" mueve la selección a otra cuenta', async () => {
    montar()
    await screen.findByText('Netflix')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Seleccionar Pago panaderia la 80' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cuenta' }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Nequi' }))
    await waitFor(() => expect(api.moverMovimientosMasivo).toHaveBeenCalledWith(['m3'], 'c2'))
  })

  it('la pulsación larga con el dedo activa el modo selección', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      montar()
      await screen.findByText('Netflix')
      const fila = document.querySelector('[data-fila="m4"]')
      fireEvent.pointerDown(fila, { pointerType: 'touch', clientX: 10, clientY: 10 })
      vi.advanceTimersByTime(600)
      await waitFor(() => expect(screen.getByText('1 seleccionado')).toBeInTheDocument())
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('vista por comercio', () => {
  it('agrupa por huella con conteo, total y categoría, y categoriza el comercio de una vez', async () => {
    montar('/movimientos?vista=comercio')
    const tarjeta = await screen.findByText('PANADERIA LA 80')
    const grupo = tarjeta.closest('[data-comercio]')
    expect(grupo).toHaveTextContent('3 movimientos')
    expect(grupo).toHaveTextContent('25.000') // 12.000 + 8.000 + 5.000
    expect(within(grupo).getByRole('button', { name: 'Categoría de PANADERIA LA 80' })).toHaveTextContent('Otros')
    await userEvent.click(within(grupo).getByRole('button', { name: 'Categoría de PANADERIA LA 80' }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: /Comida/ }))
    await waitFor(() => expect(api.recategorizarMasivo).toHaveBeenCalledWith(['m1', 'm2', 'm3'], 'Comida'))
    expect(within(grupo).getByRole('button', { name: 'Categoría de PANADERIA LA 80' })).toHaveTextContent('Comida')
  })

  it('agruparPorComercio ordena por cantidad o por monto', () => {
    const grupos = agruparPorComercio(MOVS, 'cantidad')
    expect(grupos.map((g) => g.huella)).toEqual(['panaderia', 'netflix'])
    expect(agruparPorComercio(MOVS, 'monto').map((g) => g.huella)).toEqual(['netflix', 'panaderia'])
    expect(grupos[0]).toMatchObject({ conteo: 3, total: 25000, categoria: 'Otros', mixta: false })
  })
})

describe('filtros en la URL', () => {
  it('cambiar un filtro actualiza la URL (sin llenar el historial) y se muestra como chip activo', async () => {
    montar()
    await screen.findByText('Netflix')
    await userEvent.click(screen.getByRole('button', { name: 'Filtros de fecha y cuenta' }))
    await userEvent.selectOptions(screen.getByLabelText('Filtrar por cuenta'), 'c2')
    expect(screen.getByTestId('donde')).toHaveTextContent('/movimientos?cuenta=c2')
    expect(screen.queryByText('PANADERIA LA 80 BOGOTA')).toBeNull()
    expect(screen.getByRole('button', { name: 'Quitar filtro Nequi' })).toBeInTheDocument()
    await waitFor(() => expect(api.movimientos).toHaveBeenLastCalledWith(200, 0, { cuentaId: 'c2' }))

    await userEvent.click(screen.getByRole('button', { name: 'Limpiar' }))
    expect(screen.getByTestId('donde')).toHaveTextContent(/^\/movimientos$/)
    expect(await screen.findByText('PANADERIA LA 80 BOGOTA')).toBeInTheDocument()
  })

  it('abre con los filtros del enlace y los pide al servidor', async () => {
    montar('/movimientos?cuenta=c1&desde=2026-10-02&hasta=2026-10-04&cat=Otros&vista=comercio')
    await waitFor(() =>
      expect(api.movimientos).toHaveBeenCalledWith(200, 0, {
        cuentaId: 'c1', desde: '2026-10-02', hasta: '2026-10-04', categoria: 'Otros',
      })
    )
    expect(leerFiltros(new URLSearchParams('vista=comercio&cuenta=c1')).comercio).toBe(true)
    expect(consultaServidor(leerFiltros(new URLSearchParams('revisar=1')))).toEqual({ porRevisar: true })
  })

  it('el filtro Sin categorizar muestra cuántos hay', async () => {
    montar()
    expect(await screen.findByRole('button', { name: 'Sin categorizar (3)' })).toBeInTheDocument()
  })
})

describe('volver respeta filtros y scroll', () => {
  it('al volver del detalle la lista conserva filtros, scroll y no se recarga desde cero', async () => {
    const { container } = montar('/movimientos?cuenta=c1&q=panaderia')
    await screen.findByText('PANADERIA LA 80 BOGOTA')
    const scroller = container.querySelector('.screen-enter')
    scroller.scrollTop = 640
    fireEvent.scroll(scroller)
    await waitFor(() => {
      const guardado = JSON.parse(window.sessionStorage.getItem('cuadrame:lista:/movimientos?cuenta=c1&q=panaderia'))
      expect(guardado.scroll).toBe(640)
      expect(guardado.cantidad).toBe(4)
    })

    // abrir un movimiento (ruta normal en teléfono)
    await userEvent.click(screen.getByRole('link', { name: 'PANADERIA LA 80 BOGOTA' }))
    expect(screen.getByTestId('donde')).toHaveTextContent('/movimientos/m2')
    // en el detalle se edita: el caché de la lista se parchea (invalida solo ese ítem)
    const { parchearEnCaches } = await import('../lib/useEstadoLista')
    parchearEnCaches({ id: 'm2', categoria: 'Hogar' })
    // el servidor ya tiene el cambio: la revalidación en segundo plano devuelve lo mismo
    api.movimientos.mockResolvedValue(MOVS.map((m) => (m.id === 'm2' ? { ...m, categoria: 'Hogar' } : m)))

    await userEvent.click(screen.getByRole('button', { name: 'Volver al listado' }))
    expect(screen.getByTestId('donde')).toHaveTextContent('/movimientos?cuenta=c1&q=panaderia')
    // pinta de inmediato desde el caché (sin "Cargando...") con el cambio ya aplicado
    expect(screen.queryByText('Cargando...')).toBeNull()
    expect(chipDe('PANADERIA LA 80 BOGOTA')).toHaveTextContent('Hogar')
    await waitFor(() => expect(api.movimientos).toHaveBeenCalledTimes(2)) // revalida en silencio
    expect(chipDe('PANADERIA LA 80 BOGOTA')).toHaveTextContent('Hogar')
    expect(container.querySelector('.screen-enter').scrollTop).toBe(640)
    expect(screen.getByLabelText('Buscar movimiento')).toHaveValue('panaderia')
  })

  it('al entrar desde el menú (no es volver) la lista abre desde arriba', async () => {
    window.sessionStorage.setItem('cuadrame:lista:/movimientos', JSON.stringify({ scroll: 900, ventana: 0, cantidad: 4 }))
    const { container } = render(
      <DialogosProvider>
        <MemoryRouter initialEntries={['/inicio']}>
          <Routes>
            <Route path="/inicio" element={<Link to="/movimientos">Ir a movimientos</Link>} />
            <Route path="/movimientos" element={<Movimientos />} />
          </Routes>
        </MemoryRouter>
      </DialogosProvider>
    )
    await userEvent.click(screen.getByText('Ir a movimientos'))
    await screen.findByText('Netflix')
    expect(container.querySelector('.screen-enter').scrollTop).toBe(0)
  })

  it('tras recargar la pestaña (sin caché) vuelve a pedir lo que había cargado y restaura el scroll', async () => {
    window.sessionStorage.setItem(
      'cuadrame:lista:/movimientos',
      JSON.stringify({ scroll: 900, ventana: 0, cantidad: 350 })
    )
    const pagina = (n, ini) => Array.from({ length: n }, (_, i) => ({ ...MOVS[0], id: `x${ini + i}`, descripcion: `Mov ${ini + i}` }))
    api.movimientos.mockImplementation((limite, offset) => Promise.resolve(offset === 0 ? pagina(200, 0) : pagina(150, 200)))
    const { container } = montar()
    await screen.findByText('Mov 349')
    expect(api.movimientos).toHaveBeenCalledWith(200, 0)
    expect(api.movimientos).toHaveBeenCalledWith(200, 200)
    expect(container.querySelector('.screen-enter').scrollTop).toBe(900)
  })
})
