// Centro «Traer movimientos»: rutas viejas que redirigen, enrutado por tipo de archivo, subida de varios
// archivos con uno fallido, correos con comercio y monto 0, y contadores que suman el mismo total.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const CUENTAS = [
  { id: 'c1', nombre: 'Nequi', icono: '💜', saldo: 0, moneda: 'COP', tipo: 'ahorro' },
  { id: 'c2', nombre: 'Bancolombia', icono: '🏦', saldo: 0, moneda: 'COP', tipo: 'ahorro' },
]

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  aprobarCorreo: vi.fn(),
  descartarCorreo: vi.fn(),
  obtenerReviewExtracto: vi.fn(),
  procesarExtracto: vi.fn(),
  importarFaltantes: vi.fn(),
  importarVistaPrevia: vi.fn(),
  importarConfirmar: vi.fn(),
  sincronizarCorreos: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Otros'], iconoDe: () => '' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import RedirigirAlCentro from '../components/RedirigirAlCentro'
import CorreosPorRevisar from '../components/CorreosPorRevisar'
import Sincronizacion from '../screens/Sincronizacion'
import { cantidadDe, destinoRedireccion, parsearMontoEscrito, sinDatos, tareasDeBloque, totalPorResolver } from '../lib/centro'
import { tipoDeArchivo } from '../lib/subidaMultiple'

const TAREAS = [
  { id: 'falta_clave', titulo: 'Falta la clave del PDF', detalle: '', cantidad: 1, ruta: '/sincronizacion#clave' },
  { id: 'extractos_por_conciliar', titulo: 'Extractos por conciliar', detalle: '', cantidad: 4, ruta: '/sincronizacion#extractos' },
  { id: 'sin_cuenta', titulo: 'Bancos sin cuenta', detalle: '', cantidad: 1, ruta: '/sincronizacion#cuentas' },
  { id: 'movimientos_por_categorizar', titulo: 'Movimientos por categorizar', detalle: '', cantidad: 7, ruta: '/sincronizacion#categorizar' },
  { id: 'correos_por_revisar', titulo: 'Correos por revisar', detalle: '', cantidad: 2, ruta: '/correos' },
]
const estadoCon = (tareas, extra = {}) => ({
  meses: [], cuentas: [], sin_cuenta: [], tareas, ultima_sync: '2026-10-05T10:00:00', ...extra,
})

function Destino() {
  const l = useLocation()
  return <p data-testid="destino">{JSON.stringify({ ruta: l.pathname + l.search, state: l.state })}</p>
}

const montarCentro = (entrada = '/sincronizacion') =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[entrada]}>
        <Routes>
          <Route path="/sincronizacion" element={<Sincronizacion />} />
        </Routes>
      </MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('cuadrame_gmail_sync', String(Date.now())) // sin sincronización automática al abrir
  Object.values(api).forEach((f) => f.mockReset())
  api.sincronizacionEstado.mockResolvedValue(estadoCon(TAREAS))
  api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com' })
  api.correosPendientes.mockResolvedValue([])
  api.extractosCorreo.mockResolvedValue([])
  api.clavePdfEstado.mockResolvedValue({})
})

describe('rutas viejas: redirigen al centro con state para abrir el bloque', () => {
  const montar = (entrada, ruta) =>
    render(
      <MemoryRouter initialEntries={[entrada]}>
        <Routes>
          <Route path={ruta} element={<RedirigirAlCentro ruta={ruta} />} />
          <Route path="/sincronizacion" element={<Destino />} />
        </Routes>
      </MemoryRouter>
    )
  const leer = async () => JSON.parse((await screen.findByTestId('destino')).textContent)

  it('/correos conserva ?gmail=sin_acceso (regreso de Google) y abre «Desde tu correo»', async () => {
    montar('/correos?gmail=sin_acceso', '/correos')
    expect(await leer()).toEqual({ ruta: '/sincronizacion?gmail=sin_acceso', state: { abrir: 'correo' } })
  })

  it('/conciliacion conserva historialId, cuenta y mes y abre «Subir archivos»', async () => {
    montar({ pathname: '/conciliacion', state: { historialId: 'h1', cuentaId: 'c1', mes: '2026-09' } }, '/conciliacion')
    expect(await leer()).toEqual({
      ruta: '/sincronizacion', state: { historialId: 'h1', cuentaId: 'c1', mes: '2026-09', abrir: 'subir' },
    })
  })

  it('/importar abre «Subir archivos» en modo manual y /conexiones abre el estado', async () => {
    montar('/importar', '/importar')
    expect((await leer()).state).toEqual({ abrir: 'subir', manual: true })
  })

  it('/conexiones abre el estado de las conexiones', async () => {
    montar('/conexiones', '/conexiones')
    expect((await leer()).state).toEqual({ abrir: 'estado' })
  })

  it('una ruta desconocida cae en «Por revisar»', () => {
    expect(destinoRedireccion('/otra', { search: '' }).state).toEqual({ abrir: 'revisar' })
  })

  it('al llegar con state abre el bloque y la revisión (sin salir del centro)', async () => {
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h1', cuenta_id: 'c2', banco_detectado: 'Bancolombia', total_movimientos: 1,
      review: [{ fingerprint: 'f1', fecha: '2026-09-02', descripcion: 'Compra D1', monto: 1000, tipo: 'expense', estado: 'faltante' }],
    })
    render(
      <DialogosProvider>
        <MemoryRouter initialEntries={[{ pathname: '/sincronizacion', state: { abrir: 'subir', historialId: 'h1', cuentaId: 'c2' } }]}>
          <Routes><Route path="/sincronizacion" element={<Sincronizacion />} /></Routes>
        </MemoryRouter>
      </DialogosProvider>
    )
    expect(await screen.findByTestId('revision-multiple')).toBeTruthy()
    expect(api.obtenerReviewExtracto).toHaveBeenCalledWith('h1')
    expect(screen.getByRole('button', { name: /Subir archivos/ })).toHaveAttribute('aria-expanded', 'true')
  })
})

describe('subir archivos: una sola zona, cada archivo a su lector', () => {
  const pdf = (n) => new File(['%PDF-1.4'], n, { type: 'application/pdf' })
  const csv = (n) => new File(['fecha,detalle,valor\n'], n, { type: 'text/csv' })
  const xlsx = (n) => new File(['x'], n, { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const respuestaPdf = (desc) => ({
    ok: true, historial_id: `h-${desc}`, banco_detectado: 'nequi', total_movimientos: 1, periodo_desde: '2026-09-01', periodo_hasta: '2026-09-30',
    review: [{ fingerprint: `fp-${desc}`, fecha: '2026-09-03', descripcion: desc, monto: 9000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Otros' }],
  })
  const vistaPrevia = (desc) => ({
    propuesta: [{ fila: 1, fecha: '2026-09-04', descripcion: desc, monto: 5000, tipo: 'expense', categoria: 'Otros', estado: 'nuevo' }],
    resumen: { con_error: 2 },
  })

  beforeEach(() => {
    // Sin nada por resolver, el bloque «Subir archivos» se abre solo.
    api.sincronizacionEstado.mockResolvedValue(estadoCon([]))
  })

  it('la extensión decide el lector', () => {
    expect(tipoDeArchivo('extracto.PDF')).toBe('pdf')
    expect(tipoDeArchivo('movs.csv')).toBe('tabular')
    expect(tipoDeArchivo('movs.xlsx')).toBe('tabular')
    expect(tipoDeArchivo('foto.png')).toBeNull()
  })

  it('PDF, CSV y Excel juntos: el PDF va a conciliación y los otros a la vista previa de importar', async () => {
    api.procesarExtracto.mockResolvedValue(respuestaPdf('CAFE PDF'))
    api.importarVistaPrevia.mockImplementation(({ nombre_archivo }) => Promise.resolve(vistaPrevia(`FILA ${nombre_archivo}`)))
    montarCentro()
    const zona = await screen.findByLabelText('Archivos a subir')
    fireEvent.change(zona, { target: { files: [pdf('a.pdf'), csv('b.csv'), xlsx('c.xlsx')] } })
    await userEvent.click(await screen.findByRole('button', { name: /Procesar 3 archivos/ }))
    await waitFor(() => expect(screen.getAllByText('Listo')).toHaveLength(3))
    expect(api.procesarExtracto).toHaveBeenCalledTimes(1)
    expect(api.importarVistaPrevia).toHaveBeenCalledTimes(2)
    expect(api.importarVistaPrevia.mock.calls.map((c) => c[0].nombre_archivo).sort()).toEqual(['b.csv', 'c.xlsx'])

    await userEvent.click(screen.getByRole('button', { name: /Revisar \(3 archivos\)/ }))
    expect(await screen.findByTestId('revision-multiple')).toBeTruthy()
    // Líneas que no se pudieron leer del Excel/CSV: aviso visible por archivo.
    expect(screen.getAllByTestId('aviso-descartados').length).toBe(2)
    expect(screen.getByRole('button', { name: /Seleccionar todo lo que falta \(3\)/ })).toBeTruthy()
  })

  it('subir 3 archivos con uno fallido: los otros dos se revisan y el fallido se puede reintentar', async () => {
    api.procesarExtracto
      .mockResolvedValueOnce(respuestaPdf('UNO'))
      .mockRejectedValueOnce(new Error('Servidor ocupado'))
      .mockResolvedValueOnce(respuestaPdf('TRES'))
      .mockResolvedValueOnce(respuestaPdf('DOS')) // el reintento
    api.importarFaltantes.mockResolvedValue({ ok: true, importados: 1 })
    montarCentro()
    fireEvent.change(await screen.findByLabelText('Archivos a subir'), { target: { files: [pdf('uno.pdf'), pdf('dos.pdf'), pdf('tres.pdf')] } })
    await userEvent.click(await screen.findByRole('button', { name: /Procesar 3 archivos/ }))
    expect(await screen.findByText('Servidor ocupado')).toBeTruthy()
    await waitFor(() => expect(screen.getAllByText('Listo')).toHaveLength(2))
    expect(api.procesarExtracto).toHaveBeenCalledTimes(3) // el fallo no frenó al tercero
    expect(screen.getByRole('button', { name: /Revisar \(2 archivos\)/ })).toBeTruthy()

    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    await waitFor(() => expect(screen.getAllByText('Listo')).toHaveLength(3))
  })

  it('un formato que no se puede leer se rechaza con motivo y no se envía', async () => {
    montarCentro()
    fireEvent.change(await screen.findByLabelText('Archivos a subir'), { target: { files: [new File(['x'], 'foto.png', { type: 'image/png' })] } })
    expect(await screen.findByText(/foto\.png: Formato no soportado/)).toBeTruthy()
    expect(api.procesarExtracto).not.toHaveBeenCalled()
  })
})

describe('correos por revisar: comercio real y monto', () => {
  const base = {
    id: 'k1', comercio: 'Compra en Juan Valdez', asunto: 'Compra aprobada en JUAN VALDEZ', categoria_sugerida: 'Comida', tipo_sugerido: 'expense',
    monto: 12000, banco_detectado: 'Nequi', cuenta_sugerida_id: 'c1', falta_cuenta: false, preguntar_categoria: false,
  }
  const montar = (correos, onResuelto = vi.fn()) =>
    render(<DialogosProvider><CorreosPorRevisar correos={correos} onResuelto={onResuelto} /></DialogosProvider>)

  it('muestra el comercio o concepto (no el banco) y aprueba con la cuenta sugerida', async () => {
    api.aprobarCorreo.mockResolvedValue({})
    const onResuelto = vi.fn()
    montar([base], onResuelto)
    expect(screen.getByText('Compra en Juan Valdez')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: /Aprobar/ }))
    await waitFor(() => expect(api.aprobarCorreo).toHaveBeenCalledWith('k1', 'c1'))
    expect(onResuelto).toHaveBeenCalled()
  })

  it('con monto 0 la tarjeta pide el monto: no se puede aprobar hasta escribirlo', async () => {
    api.aprobarCorreo.mockResolvedValue({})
    montar([{ ...base, monto: 0, falta_monto: true }])
    const aprobar = screen.getByRole('button', { name: /Aprobar/ })
    expect(screen.getByText(/No pude leer el monto/)).toBeTruthy()
    expect(aprobar.disabled).toBe(true)
    const campo = screen.getByLabelText('Monto de Compra en Juan Valdez')
    await userEvent.type(campo, '0')
    expect(aprobar.disabled).toBe(true) // 0 no vale
    await userEvent.clear(campo)
    await userEvent.type(campo, '25.000')
    expect(aprobar.disabled).toBe(false)
    await userEvent.click(aprobar)
    await waitFor(() => expect(api.aprobarCorreo).toHaveBeenCalledWith('k1', 'c1', { monto: 25000 }))
  })

  it('si el servidor rechaza (400) muestra el mensaje claro y deja la tarjeta', async () => {
    api.aprobarCorreo.mockRejectedValue(new Error('El monto debe ser mayor que cero: escríbelo antes de aprobar'))
    const onResuelto = vi.fn()
    montar([base], onResuelto)
    await userEvent.click(screen.getByRole('button', { name: /Aprobar/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('El monto debe ser mayor que cero')
    expect(onResuelto).not.toHaveBeenCalled()
  })

  it('el monto escrito entiende formatos colombianos', () => {
    expect(parsearMontoEscrito('25.000')).toBe(25000)
    expect(parsearMontoEscrito('1.234.567')).toBe(1234567)
    expect(parsearMontoEscrito('12.500,50')).toBe(12500.5)
    expect(parsearMontoEscrito('12,5')).toBe(12.5)
    expect(parsearMontoEscrito('$ 8000')).toBe(8000)
    expect(parsearMontoEscrito('0')).toBe(0)
    expect(parsearMontoEscrito('abc')).toBe(0)
  })
})

describe('contadores y estados', () => {
  it('cada tarea vive en un solo bloque y los contadores de bloque suman el total que ve Inicio', () => {
    expect(totalPorResolver(TAREAS)).toBe(5)
    expect(tareasDeBloque(TAREAS, 'correo').length + tareasDeBloque(TAREAS, 'revisar').length).toBe(5)
    expect(cantidadDe(TAREAS, 'extractos_por_conciliar')).toBe(4)
    expect(cantidadDe(TAREAS, 'no_existe')).toBe(0)
  })

  it('el encabezado y los bloques muestran el mismo total', async () => {
    montarCentro()
    expect(await screen.findByText('Tienes 5 cosas por resolver')).toBeTruthy()
    const correo = screen.getByRole('button', { name: /Desde tu correo/ })
    const revisar = screen.getByRole('button', { name: /Por revisar/ })
    expect(within(correo).getByLabelText('3 por resolver')).toBeTruthy()
    expect(within(revisar).getByLabelText('2 por resolver')).toBeTruthy()
    expect(screen.getAllByTestId(/^tarea-/)).toHaveLength(5)
  })

  it('si la insignia de «Por revisar» cuenta «Bancos sin cuenta», el bloque lo muestra (no queda «1» con todo vacío)', async () => {
    api.sincronizacionEstado.mockResolvedValue(estadoCon(TAREAS, { sin_cuenta: [{ banco: 'Nequi', correos: 2, extractos: 0 }] }))
    montarCentro()
    await screen.findByText('Tienes 5 cosas por resolver')
    const revisar = screen.getByRole('button', { name: /Por revisar/ })
    expect(within(revisar).getByLabelText('2 por resolver')).toBeTruthy()
    expect(document.querySelector('#sinc-sin-cuenta')).not.toBeNull()
    expect(within(document.querySelector('#sinc-sin-cuenta')).getByRole('button', { name: 'Crear cuenta Nequi' })).toBeTruthy()
  })

  it('al llegar a cero cada bloque queda en «Todo al día» y el contador desaparece', async () => {
    api.sincronizacionEstado.mockResolvedValue(estadoCon([]))
    montarCentro()
    expect(await screen.findByTestId('resumen-tareas')).toHaveTextContent('Todo al día')
    expect(screen.getByTestId('al-dia-sinc-correo')).toBeTruthy()
    expect(screen.getByTestId('al-dia-sinc-revisar')).toBeTruthy()
    expect(screen.queryByLabelText(/por resolver$/)).toBeNull()
  })

  it('sin datos muestra la barra Conecta → Trae → Revisa; con datos no', async () => {
    api.sincronizacionEstado.mockResolvedValue(estadoCon([], { ultima_sync: null }))
    api.gmailEstado.mockResolvedValue({ conectado: false })
    montarCentro()
    const pasos = await screen.findByTestId('pasos')
    expect(within(pasos).getByText('Conecta').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(sinDatos({ estado: estadoCon(TAREAS), conectado: true })).toBe(false)
  })

  it('el progreso de la sincronización se anuncia (aria-live) y es una barra accesible', async () => {
    let terminar
    api.sincronizarCorreos
      .mockResolvedValueOnce({ ok: true, completado: false, leidos: 10, total_estimado: 40 })
      .mockReturnValueOnce(new Promise((res) => { terminar = res }))
    montarCentro()
    fireEvent.click(await screen.findByRole('button', { name: 'Traer todo ahora' }))
    expect(await screen.findByText('Leí 10 de 40')).toBeTruthy()
    const barra = screen.getByRole('progressbar', { name: 'Progreso de la búsqueda de movimientos' })
    expect(barra).toHaveAttribute('aria-valuenow', '25')
    expect(barra.closest('[aria-live="polite"]')).toBeTruthy()
    terminar({ ok: true, completado: true, leidos: 40, total_estimado: 40, nuevos: 0, extractos_encontrados: 0 })
    await waitFor(() => expect(screen.queryByRole('progressbar', { name: 'Progreso de la búsqueda de movimientos' })).toBeNull())
  })

  it('error de carga con «Reintentar»', async () => {
    api.sincronizacionEstado.mockRejectedValueOnce(new Error('Sin conexión'))
    montarCentro()
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión')
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Tienes 5 cosas por resolver')).toBeTruthy()
  })
})
