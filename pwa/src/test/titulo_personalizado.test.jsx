// Nombre propio de un movimiento: edición inline en la revisión de extractos y en «Por revisar»,
// en el detalle y en la lista. El texto del banco siempre se ve en pequeño («Banco: …») y se puede recuperar.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const ORIGINAL = 'Pago PSE CODENSA SA ESP 884221'
const CUENTAS = [{ id: 'c1', nombre: 'Nequi', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: '💜' }]

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({
    categorias: [], activas: [], nombres: ['Comida', 'Hogar', 'Otros'], cargando: false, recargar: vi.fn(),
    iconoDe: () => '💳', colorDe: () => null, subsDe: () => [],
  }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import { vaciarCachesListas } from '../lib/useEstadoLista'
import { guardarBorrador, leerBorrador, borrarBorrador } from '../lib/retomar'
import { limpiarNombre, nombreDe, tieneNombrePropio } from '../lib/tituloMovimiento'
import { coincideFiltros } from '../lib/movimientosLista'
import SubidaMultiple from '../components/SubidaMultiple'
import CorreosPorRevisar from '../components/CorreosPorRevisar'
import DetalleMovimiento from '../screens/DetalleMovimiento'
import Movimientos from '../screens/Movimientos'

const montar = (ui, ruta = '/') =>
  render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter initialEntries={[ruta]}>{ui}</MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )

beforeEach(() => {
  vi.clearAllMocks()
  Object.keys(api).forEach((k) => delete api[k])
  window.sessionStorage.clear()
})

describe('helpers del nombre', () => {
  it('muestra el nombre propio y, si no hay, el del banco', () => {
    expect(nombreDe({ titulo: 'Luz', descripcion: ORIGINAL })).toBe('Luz')
    expect(nombreDe({ titulo: null, descripcion: ORIGINAL })).toBe(ORIGINAL)
    expect(tieneNombrePropio({ titulo: 'Luz', descripcion: ORIGINAL })).toBe(true)
    expect(tieneNombrePropio({ titulo: '', descripcion: ORIGINAL })).toBe(false)
  })
  it('limpia etiquetas, espacios y largo', () => {
    expect(limpiarNombre('  Recibo   <b>de</b> luz ')).toBe('Recibo de luz')
    expect(limpiarNombre('x'.repeat(120))).toHaveLength(80)
  })
  it('la búsqueda local encuentra por ambos textos', () => {
    const m = { titulo: 'Recibo de la luz', descripcion: ORIGINAL, fecha: '2026-10-01T10:00:00', categoria: 'Hogar', cuenta_id: 'c1', tipo: 'expense' }
    expect(coincideFiltros(m, { q: 'luz' })).toBe(true)
    expect(coincideFiltros(m, { q: 'codensa' })).toBe(true)
    expect(coincideFiltros(m, { q: 'netflix' })).toBe(false)
  })
  it('el borrador de la revisión guarda y devuelve los nombres', () => {
    guardarBorrador('hx', { seleccion: new Set(['a']), categorias: {}, aprender: {}, titulos: { a: 'Luz' }, recordarTitulo: { a: true } })
    const b = leerBorrador('hx')
    expect(b.titulos).toEqual({ a: 'Luz' })
    expect(b.recordarTitulo).toEqual({ a: true })
    borrarBorrador('hx')
  })
})

describe('Revisión de extracto: nombre inline', () => {
  const review = () => ({
    ok: true, historial_id: 'h1', exactos: 0, aproximados: 0, faltantes: 1, completados: 0, sobrantes: 0, total_movimientos: 1, descartados: 0,
    review: [{ fingerprint: 'fp1', fecha: '2026-10-03', descripcion: ORIGINAL, monto: 90000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Otros' }],
  })

  it('el lápiz abre el campo con el original como pista y el nombre viaja al importar', async () => {
    api.obtenerReviewExtracto = vi.fn().mockResolvedValue(review())
    api.importarFaltantes = vi.fn().mockResolvedValue({ ok: true, importados: 1 })
    montar(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} />)
    await screen.findByLabelText(`Importar ${ORIGINAL}`)
    await userEvent.click(screen.getByRole('button', { name: `Cambiar nombre de ${ORIGINAL}` }))
    const campo = screen.getByLabelText(`Nombre de ${ORIGINAL}`)
    expect(campo).toHaveAttribute('placeholder', ORIGINAL)
    await userEvent.type(campo, 'Recibo de la luz')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(screen.getByTestId('nombre-linea')).toHaveTextContent('Recibo de la luz')
    expect(screen.getByTestId('pista-banco')).toHaveTextContent(`Banco: ${ORIGINAL}`)
    await userEvent.click(screen.getByRole('button', { name: /Importar \(1\)/ }))
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalled())
    const [id, ks, , extra] = api.importarFaltantes.mock.calls[0]
    expect(id).toBe('h1')
    expect(ks).toEqual(['fp1'])
    expect(extra.titulos).toEqual({ fp1: 'Recibo de la luz' })
    expect(extra.recordar_titulo).toEqual([]) // no se recuerda si no se pidió
  })

  it('«Recordar este nombre» solo viaja si se marca, y «Volver al original» lo quita', async () => {
    api.obtenerReviewExtracto = vi.fn().mockResolvedValue(review())
    api.importarFaltantes = vi.fn().mockResolvedValue({ ok: true, importados: 1 })
    montar(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} />)
    await screen.findByLabelText(`Importar ${ORIGINAL}`)
    await userEvent.click(screen.getByRole('button', { name: `Cambiar nombre de ${ORIGINAL}` }))
    await userEvent.type(screen.getByLabelText(`Nombre de ${ORIGINAL}`), 'Luz')
    await userEvent.click(screen.getByRole('checkbox', { name: /Recordar este nombre para este comercio/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    // el borrador guarda el nombre (sale y vuelve sin perderlo)
    await waitFor(() => expect(leerBorrador('h1')?.titulos).toEqual({ fp1: 'Luz' }))
    expect(leerBorrador('h1').recordarTitulo).toEqual({ fp1: true })
    // volver al original
    await userEvent.click(screen.getByRole('button', { name: `Cambiar nombre de ${ORIGINAL}` }))
    await userEvent.click(screen.getByRole('button', { name: 'Volver al original' }))
    expect(screen.getByTestId('nombre-linea')).toHaveTextContent(ORIGINAL)
    expect(screen.queryByTestId('pista-banco')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /Importar \(1\)/ }))
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalled())
    expect(api.importarFaltantes.mock.calls[0][3].titulos).toBeUndefined()
  })

  it('un borrador con nombre vuelve al reabrir la revisión', async () => {
    guardarBorrador('h1', { seleccion: new Set(['fp1']), categorias: {}, aprender: {}, titulos: { fp1: 'Luz de casa' }, recordarTitulo: {} })
    api.obtenerReviewExtracto = vi.fn().mockResolvedValue(review())
    montar(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} />)
    expect(await screen.findByText('Luz de casa')).toBeInTheDocument()
    expect(screen.getByTestId('pista-banco')).toHaveTextContent(ORIGINAL)
  })
})

describe('Correos por revisar: nombre antes de aprobar', () => {
  it('el nombre elegido se envía al aprobar', async () => {
    api.aprobarCorreo = vi.fn().mockResolvedValue({})
    const correo = {
      id: 'k1', comercio: 'Compra en Juan Valdez', asunto: 'Compra aprobada', monto: 12000, tipo_sugerido: 'expense',
      categoria_sugerida: 'Comida', cuenta_sugerida_id: 'c1', banco_detectado: 'Nu',
    }
    montar(<CorreosPorRevisar correos={[correo]} onResuelto={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar nombre de Compra en Juan Valdez' }))
    await userEvent.type(screen.getByLabelText('Nombre de Compra en Juan Valdez'), 'Café con Ana')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(screen.getByTestId('pista-banco')).toHaveTextContent('Compra en Juan Valdez')
    await userEvent.click(screen.getByRole('button', { name: /Aprobar$/ }))
    await waitFor(() => expect(api.aprobarCorreo).toHaveBeenCalledWith('k1', 'c1', { titulo: 'Café con Ana' }))
  })

  it('sin nombre propio la llamada queda igual que antes', async () => {
    api.aprobarCorreo = vi.fn().mockResolvedValue({})
    const correo = { id: 'k2', comercio: 'Netflix', asunto: 'Cobro', monto: 30000, tipo_sugerido: 'expense', categoria_sugerida: 'Comida', cuenta_sugerida_id: 'c1' }
    montar(<CorreosPorRevisar correos={[correo]} onResuelto={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Aprobar$/ }))
    await waitFor(() => expect(api.aprobarCorreo).toHaveBeenCalledWith('k2', 'c1'))
  })
})

describe('Detalle del movimiento', () => {
  const mov = (extra = {}) => ({
    id: 'm1', cuenta_id: 'c1', fecha: '2026-10-03T10:00:00', descripcion: ORIGINAL, categoria: 'Hogar', tipo: 'expense',
    monto: 90000, fuente: 'conciliacion_extracto', notas: '', titulo: null, cat_confirmada: true, ...extra,
  })
  const montarDetalle = () =>
    montar(
      <Routes>
        <Route path="/movimientos/:id" element={<DetalleMovimiento />} />
      </Routes>,
      '/movimientos/m1'
    )

  it('muestra el nombre propio con el del banco en pequeño y deja volver al original', async () => {
    api.movimiento = vi.fn().mockResolvedValue(mov({ titulo: 'Recibo de la luz' }))
    api.similaresConteo = vi.fn().mockResolvedValue({ conteo: 0 })
    api.editarMovimiento = vi.fn().mockResolvedValue(mov({ titulo: null }))
    montarDetalle()
    expect(await screen.findByTestId('detalle-descripcion')).toHaveTextContent('Recibo de la luz')
    expect(screen.getByTestId('pista-banco')).toHaveTextContent(`Banco: ${ORIGINAL}`)
    await userEvent.click(screen.getByRole('button', { name: `Cambiar nombre de ${ORIGINAL}` }))
    await userEvent.click(screen.getByRole('button', { name: 'Volver al original' }))
    await waitFor(() => expect(api.editarMovimiento).toHaveBeenCalledWith('m1', { titulo: '' }))
    await waitFor(() => expect(screen.getByTestId('detalle-descripcion')).toHaveTextContent(ORIGINAL))
    expect(screen.queryByTestId('pista-banco')).toBeNull()
  })

  it('guarda un nombre nuevo y lo recuerda solo si se marca', async () => {
    api.movimiento = vi.fn().mockResolvedValue(mov())
    api.similaresConteo = vi.fn().mockResolvedValue({ conteo: 1 })
    api.editarMovimiento = vi.fn().mockResolvedValue(mov({ titulo: 'Luz' }))
    montarDetalle()
    await screen.findByTestId('detalle-descripcion')
    await userEvent.click(screen.getByRole('button', { name: `Cambiar nombre de ${ORIGINAL}` }))
    await userEvent.type(screen.getByLabelText(`Nombre de ${ORIGINAL}`), 'Luz')
    const casilla = screen.getByRole('checkbox', { name: /Recordar este nombre para este comercio/ })
    expect(casilla).not.toBeChecked() // el comercio no se repite lo suficiente: apagada por defecto
    await userEvent.click(casilla)
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(api.editarMovimiento).toHaveBeenCalledWith('m1', { titulo: 'Luz', recordar_titulo: true }))
  })

  it('con el comercio repetido ≥ 4 veces la casilla sale marcada', async () => {
    api.movimiento = vi.fn().mockResolvedValue(mov())
    api.similaresConteo = vi.fn().mockResolvedValue({ conteo: 5 })
    montarDetalle()
    await screen.findByTestId('detalle-descripcion')
    await userEvent.click(screen.getByRole('button', { name: `Cambiar nombre de ${ORIGINAL}` }))
    await userEvent.type(screen.getByLabelText(`Nombre de ${ORIGINAL}`), 'Luz')
    await waitFor(() => expect(screen.getByRole('checkbox', { name: /Recordar este nombre/ })).toBeInTheDocument())
  })
})

describe('Lista de movimientos (móvil)', () => {
  const matchOriginal = window.matchMedia
  afterEach(() => {
    window.matchMedia = matchOriginal
  })

  it('muestra el nombre propio con el original en pequeño y el lápiz lo cambia', async () => {
    vaciarCachesListas()
    window.localStorage.clear()
    window.matchMedia = (q) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
    const m = {
      id: 'm1', cuenta_id: 'c1', fecha: new Date().toISOString(), descripcion: ORIGINAL, categoria: 'Hogar', tipo: 'expense',
      monto: 90000, fuente: 'manual', notas: '', titulo: 'Recibo de la luz', cat_confirmada: true, cat_origen: null,
    }
    api.movimientos = vi.fn().mockResolvedValue([m])
    api.conteoPorRevisar = vi.fn().mockResolvedValue({ auto: 0, otros: 0, total: 0 })
    api.similaresConteo = vi.fn().mockResolvedValue({ conteo: 0 })
    api.editarMovimiento = vi.fn().mockResolvedValue({ ...m, titulo: 'Luz' })
    montar(<Movimientos />, '/movimientos')
    const fila = await screen.findByText('Recibo de la luz')
    expect(fila).toBeInTheDocument()
    expect(screen.getByTestId('pista-banco')).toHaveTextContent(ORIGINAL)
    await userEvent.click(screen.getByRole('button', { name: `Cambiar nombre de ${ORIGINAL}` }))
    const campo = await screen.findByLabelText(`Nombre de ${ORIGINAL}`)
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Luz')
    await userEvent.click(within(campo.closest('[data-testid="editor-nombre"]')).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(api.editarMovimiento).toHaveBeenCalledWith('m1', { titulo: 'Luz' }))
    expect(await screen.findByText('Luz')).toBeInTheDocument()
  })
})
