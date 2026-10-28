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

// Los interruptores viven en la hoja «Conexiones y claves».
const abrirConexion = () => fireEvent.click(screen.getByTestId('abrir-conexiones'))
const montarTarjetas = (correos) =>
  render(<DialogosProvider><CorreosPorRevisar correos={correos} onResuelto={vi.fn()} /></DialogosProvider>)

const montar = (ruta = '/sincronizacion') =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[ruta]}>
        <Routes>
          <Route path="/sincronizacion" element={<Sincronizacion />} />
          <Route path="/movimientos-correo" element={<Sincronizacion modo="correo" />} />
        </Routes>
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
    expect(resumenCarriles(TAREAS)).toBe('3 movimientos por revisar · 3 extractos por revisar')
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
    expect(resumenLectura('extractos', { extractos_encontrados: 0 })).toMatch(/no hay extractos nuevos/i)
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

describe('Traer extractos y Movimientos del correo: los dos usos del correo', () => {
  it('los dos usos del correo tienen su interruptor en «Conexiones y claves»; la pantalla principal no los repite', async () => {
    montar()
    await screen.findByTestId('paso-guiado')
    expect(screen.queryByTestId('carril-movimientos')).toBeNull()
    expect(screen.queryByTestId('carril-extractos')).toBeNull()
    abrirConexion()
    expect(within(await screen.findByTestId('interruptor-movimientos')).getByRole('switch', { name: /Leer notificaciones/i })).toBeChecked()
    expect(within(screen.getByTestId('interruptor-extractos')).getByRole('switch', { name: /Leer extractos/i })).toBeChecked()
  })

  it('si falla un uso se dice cuál y el otro sigue funcionando (cada pantalla lee solo el suyo)', async () => {
    api.sincronizarCorreos.mockImplementation(async (p) => (p?.tipo === 'extractos'
      ? { ok: false, error: 'No se pudo sincronizar tus correos.' }
      : { ok: true, completado: true, nuevos: 1, tipo: 'movimientos' }))
    // «Movimientos del correo» sigue funcionando aunque la lectura de extractos esté fallando...
    const vistaCorreo = montar('/movimientos-correo')
    fireEvent.click(await screen.findByRole('button', { name: 'Buscar ahora' }))
    expect(await screen.findByTestId('resumen-busqueda')).toHaveTextContent('Encontré 1 movimiento nuevo.')
    vistaCorreo.unmount()
    // ...y «Traer extractos» dice que ESA lectura no pudo.
    montar()
    fireEvent.click(await screen.findByRole('button', { name: 'Buscar ahora' }))
    expect(await screen.findByRole('alert')).toBeTruthy() // la lectura de extractos falló y se dice, sin tocar la de avisos
    abrirConexion()
    expect(await screen.findByText(/^Extractos: /i)).toBeTruthy()
  })

  it('el interruptor guarda solo ese carril y deja el otro como estaba', async () => {
    montar()
    await screen.findByTestId('paso-guiado')
    abrirConexion()
    const sw = within(await screen.findByTestId('interruptor-extractos')).getByRole('switch')
    // Al guardar, la pantalla vuelve a pedir el estado: el servidor ya responde con el cambio.
    api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', leer_movimientos: true, leer_extractos: false })
    fireEvent.click(sw)
    await waitFor(() => expect(api.gmailLectura).toHaveBeenCalledWith({ leer_extractos: false }))
    // Apagado solo ese uso: el otro sigue encendido.
    await waitFor(() => expect(within(screen.getByTestId('interruptor-extractos')).getByRole('switch')).not.toBeChecked())
    expect(within(screen.getByTestId('interruptor-movimientos')).getByRole('switch')).toBeChecked()
  })

  it('con un uso apagado, «Buscar ahora» solo lee el encendido', async () => {
    api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', leer_movimientos: false, leer_extractos: true })
    api.sincronizarCorreos.mockResolvedValue({ ok: true, completado: true, extractos_encontrados: 0, tipo: 'extractos' })
    montar()
    fireEvent.click(await screen.findByRole('button', { name: 'Buscar ahora' }))
    await waitFor(() => expect(api.sincronizarCorreos).toHaveBeenCalledTimes(1))
    expect(api.sincronizarCorreos).toHaveBeenCalledWith({ tipo: 'extractos' })
  })

  it('«¿Cuál es la diferencia?» explica los dos usos con un ejemplo cada uno', async () => {
    montar()
    expect(screen.queryByTestId('ayuda-carriles')).toBeNull()
    await screen.findByTestId('paso-guiado')
    abrirConexion()
    fireEvent.click(await screen.findByRole('button', { name: /¿Cuál es la diferencia\?/ }))
    const ayuda = screen.getByTestId('ayuda-carriles')
    expect(ayuda.textContent).toMatch(/Compra por \$45\.000 en Éxito/)
    expect(ayuda.textContent).toMatch(/PDF de septiembre/)
  })

  it('no hay listas de «Por hacer» por sección: un paso principal y lo demás espera su turno', async () => {
    montar()
    await screen.findByTestId('paso-guiado')
    expect(screen.queryByTestId('por-hacer-extractos')).toBeNull()
    expect(screen.queryByTestId('por-hacer-movimientos')).toBeNull()
    expect(screen.queryByTestId('por-hacer-general')).toBeNull()
    expect(screen.getAllByTestId(/^tarea-/)).toHaveLength(1)
    expect(screen.getByTestId('tarea-falta_clave')).toBeTruthy()
  })

  it('«Movimientos del correo» → «Ver todo» no repite la lista: ofrece «Ver los N por revisar»', async () => {
    montar('/movimientos-correo')
    fireEvent.click(await screen.findByTestId('ver-todo'))
    fireEvent.click(await screen.findByTestId('tab-correos'))
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
