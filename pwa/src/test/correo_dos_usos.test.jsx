// El correo en DOS usos: «Movimientos» y «Extractos», cada uno en su sección con su botón, última vez, contadores
// y error; los interruptores y la ayuda viven en «Conexión de Gmail». «Por hacer» propio por sección y aprobar en bloque.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [{ id: 'bc', nombre: 'Bancolombia Ahorros', icono: '🏦', saldo: 0, moneda: 'COP', tipo: 'ahorro' }]

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  gmailLectura: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  aprobarCorreo: vi.fn(),
  descartarCorreo: vi.fn(),
  sincronizarCorreos: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Otros'], iconoDe: (n) => (n === 'Comida' ? '🍔' : '') }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import CorreosPorRevisar from '../components/CorreosPorRevisar'
import Sincronizacion from '../screens/Sincronizacion'
import EtiquetaOrigen from '../components/EtiquetaOrigen'
import { gruposDeTareas, resumenCarriles, resumenLectura } from '../lib/carriles'
import { faltaConfirmarExtracto } from '../lib/canales'
import { sincronizarCarriles } from '../lib/sincronizarGmail'

const TAREAS = [
  { id: 'falta_clave', titulo: 'Falta la clave del PDF', detalle: '', cantidad: 1, ruta: '/x', carril: 'extractos' },
  { id: 'extractos_por_conciliar', titulo: 'Extractos por conciliar', detalle: '', cantidad: 2, ruta: '/x', carril: 'extractos' },
  { id: 'sin_cuenta', titulo: 'Bancos sin cuenta', detalle: '', cantidad: 1, ruta: '/x', carril: null },
  { id: 'correos_por_revisar', titulo: 'Movimientos nuevos del correo', detalle: '', cantidad: 3, ruta: '/correos', carril: 'movimientos' },
]
const CARRILES = {
  movimientos: { activo: true, ultima_vez: new Date(Date.now() - 2 * 3600000).toISOString().slice(0, 19), por_revisar: 3, ya_registrados: 4, provisionales: 2, nuevos: 3, leidos: 9 },
  extractos: { activo: true, ultima_vez: null, encontrados: 5, por_conciliar: 2, con_clave_pendiente: 1, al_dia: 2, nuevos: 0 },
}
const estado = (extra = {}) => ({ meses: [], cuentas: [], sin_cuenta: [], tareas: TAREAS, ultima_sync: '2026-10-05T10:00:00', carriles: CARRILES, ...extra })
const correo = (id, extra = {}) => ({
  id, comercio: `Comercio ${id}`, asunto: 'Compra', monto: 10000, tipo_sugerido: 'expense', categoria_sugerida: 'Comida',
  cuenta_sugerida_id: 'bc', banco_detectado: 'Bancolombia', ...extra,
})

// «Conexión de Gmail» está plegada por defecto (modo simple): se abre para llegar a los interruptores.
const abrirConexion = () => fireEvent.click(screen.getByTestId('bloque-sinc-conexion').querySelector('h2 button'))
const montarTarjetas = (correos) =>
  render(<DialogosProvider><CorreosPorRevisar correos={correos} onResuelto={vi.fn()} /></DialogosProvider>)

const montar = () =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={['/sincronizacion']}>
        <Routes><Route path="/sincronizacion" element={<Sincronizacion />} /></Routes>
      </MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
  Object.values(api).forEach((f) => f.mockReset())
  api.sincronizacionEstado.mockResolvedValue(estado())
  api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', leer_movimientos: true, leer_extractos: true })
  api.gmailLectura.mockResolvedValue({ ok: true })
  api.correosPendientes.mockResolvedValue([])
  api.extractosCorreo.mockResolvedValue([])
  api.clavePdfEstado.mockResolvedValue({})
})

describe('lib/carriles', () => {
  it('el resumen no mezcla los dos conteos', () => {
    expect(resumenCarriles(TAREAS)).toBe('3 movimientos por revisar · 3 extractos por conciliar')
    expect(resumenCarriles([{ id: 'correos_por_revisar', cantidad: 1 }])).toBe('1 movimiento por revisar')
    expect(resumenCarriles([{ id: 'sin_cuenta', cantidad: 2 }])).toBe('')
  })

  it('agrupa las tareas por carril y deja lo demás en «Otras cosas»', () => {
    const g = gruposDeTareas(TAREAS)
    expect(g.map((x) => x.clave)).toEqual(['extractos', 'general', 'movimientos'])
    expect(g[0].nombre).toBe('Extractos')
    expect(g[1].nombre).toBe('Otras cosas')
    expect(gruposDeTareas([TAREAS[2]])[0].nombre).toBe('') // solo lo general: sin título
  })

  it('dice lo que pasó en cada lectura', () => {
    expect(resumenLectura('movimientos', { nuevos: 2 })).toBe('Encontré 2 movimientos nuevos.')
    expect(resumenLectura('extractos', { extractos_encontrados: 0 })).toMatch(/no hay extractos nuevos/)
    expect(resumenLectura('extractos', { aviso: 'Están apagados' })).toBe('Están apagados')
  })

  it('sincronizarCarriles: si falla uno, el otro igual se lee y no se lee el apagado', async () => {
    api.sincronizarCorreos.mockImplementation(async (p) => (p?.tipo === 'movimientos' ? { ok: false, error: 'Falló' } : { ok: true, completado: true, extractos_encontrados: 1 }))
    const r = await sincronizarCarriles({ activos: { movimientos: true, extractos: true } })
    expect(r.movimientos.error).toBe('Falló')
    expect(r.extractos.r.extractos_encontrados).toBe(1)
    api.sincronizarCorreos.mockClear()
    const solo = await sincronizarCarriles({ activos: { movimientos: false, extractos: true } })
    expect(Object.keys(solo)).toEqual(['extractos'])
    expect(api.sincronizarCorreos).toHaveBeenCalledTimes(1)
  })

  it('la etiqueta «falta confirmar con el extracto» solo sale en lo que nació del correo sin respaldo', () => {
    expect(faltaConfirmarExtracto('correo', ['correo'])).toBe(true)
    expect(faltaConfirmarExtracto('correo', ['correo', 'extracto'])).toBe(false)
    expect(faltaConfirmarExtracto('correo', undefined)).toBe(false)
    expect(faltaConfirmarExtracto('manual', ['manual'])).toBe(false)
  })
})

describe('EtiquetaOrigen', () => {
  it('marca como provisional el movimiento del correo que aún no respalda un extracto', () => {
    const { rerender } = render(<EtiquetaOrigen origen="correo" canales={['correo']} />)
    expect(screen.getByText('Falta confirmar con el extracto')).toBeTruthy()
    rerender(<EtiquetaOrigen origen="correo" canales={['correo', 'extracto']} />)
    expect(screen.queryByText('Falta confirmar con el extracto')).toBeNull()
    expect(screen.getByText('confirmado por extracto')).toBeTruthy()
  })
})

describe('Traer movimientos: las dos tarjetas del correo', () => {
  it('muestra «Movimientos» y «Extractos» como secciones propias, cada una con su botón, última vez y contadores; los interruptores van en la conexión', async () => {
    montar()
    const mov = await screen.findByTestId('carril-movimientos')
    const ext = screen.getByTestId('carril-extractos')
    expect(within(screen.getByTestId('bloque-sinc-movimientos')).getByRole('heading', { level: 2, name: /^Movimientos/ })).toBeTruthy()
    expect(within(screen.getByTestId('bloque-sinc-extractos')).getByRole('heading', { level: 2, name: /^Extractos/ })).toBeTruthy()
    expect(within(mov).getByText(/Las notificaciones de tu banco: así ves en el momento lo que gastas/)).toBeTruthy()
    expect(within(ext).getByText(/El extracto mensual del banco: sirve para confirmar y cuadrar el mes/)).toBeTruthy()
    abrirConexion()
    expect(within(screen.getByTestId('interruptor-movimientos')).getByRole('switch', { name: /Leer notificaciones/i })).toBeChecked()
    expect(within(screen.getByTestId('interruptor-extractos')).getByRole('switch', { name: /Leer extractos/i })).toBeChecked()
    expect(within(mov).getByText('3 por revisar')).toBeTruthy()
    // los contadores de una sección no aparecen en la otra
    expect(within(mov).queryByText('1 necesita clave')).toBeNull()
    expect(within(ext).queryByText('3 por revisar')).toBeNull()
    expect(within(mov).getByText('2 faltan confirmar con el extracto')).toBeTruthy()
    expect(within(ext).getByText('1 necesita clave')).toBeTruthy()
    expect(within(mov).getByTestId('ultima-movimientos').textContent).toMatch(/Última vez hace 2 h/)
    expect(within(ext).getByTestId('ultima-extractos').textContent).toMatch(/Aún no he leído/)
  })

  it('cada botón trae solo su carril', async () => {
    api.sincronizarCorreos.mockResolvedValue({ ok: true, completado: true, extractos_encontrados: 2, tipo: 'extractos' })
    montar()
    fireEvent.click(within(await screen.findByTestId('carril-extractos')).getByRole('button', { name: 'Buscar extractos' }))
    expect(await screen.findByTestId('resultado-extractos')).toHaveTextContent('Encontré 2 extractos.')
    expect(api.sincronizarCorreos).toHaveBeenCalledTimes(1)
    expect(api.sincronizarCorreos).toHaveBeenCalledWith({ tipo: 'extractos' })
    expect(screen.queryByTestId('resultado-movimientos')).toBeNull()
  })

  it('si falla un carril se dice cuál y el otro sigue funcionando', async () => {
    api.sincronizarCorreos.mockImplementation(async (p) => (p?.tipo === 'extractos'
      ? { ok: false, error: 'No se pudo sincronizar tus correos.' }
      : { ok: true, completado: true, nuevos: 1, tipo: 'movimientos' }))
    montar()
    fireEvent.click(await screen.findByRole('button', { name: 'Traer todo ahora' }))
    expect(await screen.findByTestId('error-extractos')).toHaveTextContent('Extractos')
    expect(screen.getByTestId('resultado-movimientos')).toHaveTextContent('Encontré 1 movimiento nuevo.')
    expect(screen.queryByTestId('error-movimientos')).toBeNull()
  })

  it('el interruptor guarda solo ese carril y deja el otro como estaba', async () => {
    montar()
    await screen.findByTestId('carril-extractos')
    abrirConexion()
    const sw = within(screen.getByTestId('interruptor-extractos')).getByRole('switch')
    // Al guardar, la pantalla vuelve a pedir el estado: el servidor ya responde con el cambio.
    api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', leer_movimientos: true, leer_extractos: false })
    fireEvent.click(sw)
    await waitFor(() => expect(api.gmailLectura).toHaveBeenCalledWith({ leer_extractos: false }))
    // Apagado: lo dice con claridad y ya no ofrece el botón de buscar.
    expect(await screen.findByTestId('apagado-extractos')).toHaveTextContent('no leo ni guardo extractos')
    expect(within(screen.getByTestId('carril-movimientos')).getByRole('button', { name: 'Traer movimientos' })).toBeTruthy()
  })

  it('con un carril apagado, «Traer todo» solo lee el encendido', async () => {
    api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', leer_movimientos: false, leer_extractos: true })
    api.sincronizarCorreos.mockResolvedValue({ ok: true, completado: true, extractos_encontrados: 0, tipo: 'extractos' })
    montar()
    fireEvent.click(await screen.findByRole('button', { name: 'Traer todo ahora' }))
    await waitFor(() => expect(api.sincronizarCorreos).toHaveBeenCalledTimes(1))
    expect(api.sincronizarCorreos).toHaveBeenCalledWith({ tipo: 'extractos' })
  })

  it('«¿Cuál es la diferencia?» explica los dos usos con un ejemplo cada uno', async () => {
    montar()
    expect(screen.queryByTestId('ayuda-carriles')).toBeNull()
    await screen.findByTestId('carril-movimientos')
    abrirConexion()
    fireEvent.click(await screen.findByRole('button', { name: /¿Cuál es la diferencia\?/ }))
    const ayuda = screen.getByTestId('ayuda-carriles')
    expect(ayuda.textContent).toMatch(/Compra por \$45\.000 en Éxito/)
    expect(ayuda.textContent).toMatch(/PDF de septiembre/)
  })

  it('cada sección tiene su «Por hacer» propio y lo demás va en «Otras cosas por hacer»', async () => {
    montar()
    const grupoExt = await screen.findByTestId('por-hacer-extractos')
    const grupoMov = screen.getByTestId('por-hacer-movimientos')
    expect(within(grupoExt).getByTestId('tarea-falta_clave')).toBeTruthy()
    expect(within(grupoExt).queryByTestId('tarea-correos_por_revisar')).toBeNull()
    expect(within(grupoMov).getByTestId('tarea-correos_por_revisar')).toBeTruthy()
    expect(within(screen.getByTestId('por-hacer-general')).getByTestId('tarea-sin_cuenta')).toBeTruthy()
    expect(screen.getByTestId('resumen-carriles')).toHaveTextContent('3 movimientos por revisar · 3 extractos por conciliar')
  })

  it('la tarjeta de Movimientos no repite la lista: ofrece «Ver los N por revisar»', async () => {
    montar()
    const boton = await screen.findByTestId('ver-por-revisar')
    expect(boton).toHaveTextContent('Ver los 3 por revisar')
    expect(screen.queryByTestId('correo-a')).toBeNull()
  })
})

describe('Movimientos del correo por revisar (tarjetas)', () => {
  it('muestra comercio, monto, categoría con emoji y aprueba en bloque los que parecen correctos', async () => {
    const lista = [
      correo('a'), correo('b'),
      correo('c', { preguntar_categoria: true, categoria_sugerida: 'Otros' }), // este no parece correcto: pide categoría
    ]
    api.aprobarCorreo.mockResolvedValue({})
    montarTarjetas(lista)
    expect((await screen.findAllByText(/🍔 Comida/, { selector: 'p' })).length).toBe(2)
    const bloque = await screen.findByTestId('aprobar-correctos')
    expect(bloque).toHaveTextContent('Aprobar los 2 que parecen correctos')
    fireEvent.click(bloque)
    await waitFor(() => expect(api.aprobarCorreo).toHaveBeenCalledTimes(2))
    expect(api.aprobarCorreo).toHaveBeenCalledWith('a', 'bc')
    expect(api.aprobarCorreo).toHaveBeenCalledWith('b', 'bc')
    expect(api.aprobarCorreo).not.toHaveBeenCalledWith('c', expect.anything())
  })

  it('con menos de dos correctos no ofrece aprobar en bloque', async () => {
    montarTarjetas([correo('a')])
    await screen.findByTestId('correo-a')
    expect(screen.queryByTestId('aprobar-correctos')).toBeNull()
  })
})
