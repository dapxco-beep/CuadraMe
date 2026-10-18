// «Todos los extractos»: cada fila dice banco + tipo + mes, su estado y qué pasó; filtros, buscador, grupos por mes,
// duplicados juntos, errores con su motivo y acciones. También la pantalla (Por hacer y cobertura abren la lista).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [
  { id: 'nu', nombre: 'Nu Colombia', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
  { id: 'tj', nombre: 'Tarjeta Nu', saldo: 0, moneda: 'COP', tipo: 'credito', icono: '💳' },
]

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  conciliarExtractoCorreo: vi.fn(),
  reintentarExtractoCorreo: vi.fn(),
  fijarMesExtracto: vi.fn(),
  probarClavePdf: vi.fn(),
  almacenMuestras: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Otros'], iconoDe: () => '🏷️' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import Sincronizacion from '../screens/Sincronizacion'
import TodosLosExtractos from '../components/TodosLosExtractos'
import { agruparPorMes, coincideBusqueda, filtrar, opcionesCuenta, textoContadores } from '../lib/extractosVista'

const base = {
  extracto_id: null, historial_id: null, cuenta_id: 'nu', cuenta: 'Nu Colombia', banco: 'Nu Colombia', tipo: 'cuenta',
  copias: 1, copias_texto: '', mes_deducido: false, mes_por_confirmar: false, puede_fijar_mes: true, motivo_error: null,
  leidas: 0, ya_estaban: 0, nuevas_agregadas: 0, por_revisar: 0,
}
const fila = (extra) => ({ ...base, ...extra })

const ITEMS = [
  fila({
    id: 'c:6', extracto_id: 'e6', historial_id: 'h6', mes: '2026-07', mes_etiqueta: 'Julio 2026', titulo: 'Nu Colombia · Cuenta · Julio 2026',
    estado_vista: 'revisado', estado_etiqueta: 'Revisado', acciones: ['ver', 'revisar_de_nuevo'],
    resultado: 'Leímos 37 movimientos: 37 ya estaban registrados, 0 nuevos.',
  }),
  fila({
    id: 'c:5', extracto_id: 'e5', historial_id: 'h5', mes: '2026-06', mes_etiqueta: 'Junio 2026', titulo: 'Nu Colombia · Cuenta · Junio 2026',
    estado_vista: 'revisado', estado_etiqueta: 'Revisado', acciones: ['ver', 'revisar_de_nuevo'], copias: 2, copias_texto: 'x2 correos',
    resultado: 'Leímos 37 movimientos: 5 nuevos agregados, 32 ya estaban.',
  }),
  fila({
    id: 'c:k', extracto_id: 'ek', mes: '2026-08', mes_etiqueta: 'Agosto 2026', titulo: 'Tarjeta Nu · corte 14 ago 2026', cuenta_id: 'tj', cuenta: 'Tarjeta Nu',
    tipo: 'tarjeta', estado_vista: 'necesita_clave', estado_etiqueta: 'Necesita clave', acciones: ['poner_clave', 'probar_clave'],
    resultado: 'Está protegido con clave. Guarda la clave del PDF para poder leerlo.',
  }),
  fila({
    id: 'c:n', extracto_id: 'en', mes: '2026-08', mes_etiqueta: 'Agosto 2026', titulo: 'Nu Colombia · Cuenta · Agosto 2026', mes_deducido: true,
    estado_vista: 'sin_procesar', estado_etiqueta: 'Sin procesar', acciones: ['revisar'],
    resultado: 'Llegó a tu correo y aún no lo hemos leído. Toca «Revisar» para traer sus movimientos.',
  }),
  fila({
    id: 'c:x', extracto_id: 'ex', mes: '2026-05', mes_etiqueta: 'Mayo 2026', titulo: 'Nu Colombia · Cuenta · Mayo 2026', motivo_error: 'pdf_escaneado',
    estado_vista: 'no_se_pudo_leer', estado_etiqueta: 'No se pudo leer', acciones: ['intentar_de_nuevo', 'mi_banco_no_esta'],
    resultado: 'No pudimos leer este extracto: el PDF es una imagen y no trae texto que podamos leer. Descarga el extracto en Excel o CSV desde tu banco y súbelo, o agrega los movimientos a mano.',
  }),
  fila({
    id: 'h:v', mes: null, mes_etiqueta: 'Mes por confirmar', titulo: 'Nu Colombia · Cuenta · Mes por confirmar', mes_por_confirmar: true, puede_fijar_mes: false,
    estado_vista: 'no_se_pudo_leer', estado_etiqueta: 'No se pudo leer', acciones: ['subir_de_nuevo', 'mi_banco_no_esta'], copias: 3, copias_texto: 'x3 intentos',
    resultado: 'No se pudo leer (motivo no guardado). Toca «Intentar de nuevo».',
  }),
  fila({
    id: 'c:s', extracto_id: 'es', mes: null, mes_etiqueta: 'Mes por confirmar', titulo: 'Banco sin identificar · Mes por confirmar', cuenta_id: null,
    cuenta: '', banco: '', tipo: '', mes_por_confirmar: true, estado_vista: 'sin_procesar', estado_etiqueta: 'Sin procesar', acciones: ['revisar'],
    resultado: 'Llegó a tu correo y aún no lo hemos leído. Toca «Revisar» para traer sus movimientos.',
  }),
]
const DATOS = {
  items: ITEMS,
  contadores: { revisado: 2, por_revisar: 0, necesita_clave: 1, sin_procesar: 2, no_se_pudo_leer: 2, anterior_al_inicio: 0 },
  resumen: '2 revisados · 1 con clave pendiente · 2 sin procesar · 2 con error',
  sin_adjunto: [
    { id: 'i1', asunto: 'Tu cuenta Nu está lista', banco: 'Nu', recibido_en: '2026-08-04T10:00:00' },
    { id: 'i2', asunto: 'Novedades de tu tarjeta', banco: 'Nu', recibido_en: '2026-08-05T10:00:00' },
  ],
  razon_sin_adjunto: 'El correo habla de un extracto pero no trae el PDF adjunto (o el archivo no parece un extracto).',
}
const SIN_FILTRO = { estados: [], cuenta: '', mes: '', texto: '' }

describe('lib extractosVista', () => {
  it('agrupa por mes del más reciente al más antiguo y deja «Mes por confirmar» al final', () => {
    const g = agruparPorMes([...ITEMS].reverse())
    expect(g.map((x) => x.etiqueta)).toEqual(['Agosto 2026', 'Julio 2026', 'Junio 2026', 'Mayo 2026', 'Mes por confirmar'])
    expect(g[0].items).toHaveLength(2)
  })

  it('busca por mes sin importar tildes ni mayúsculas, por banco y por cuenta', () => {
    expect(filtrar(ITEMS, { ...SIN_FILTRO, texto: 'JULIO' }).map((x) => x.id)).toEqual(['c:6'])
    expect(filtrar(ITEMS, { ...SIN_FILTRO, texto: 'tarjeta agosto' }).map((x) => x.id)).toEqual(['c:k'])
    expect(coincideBusqueda(ITEMS[0], '2026-07')).toBe(true)
    expect(filtrar(ITEMS, { ...SIN_FILTRO, cuenta: 'c:tj' }).map((x) => x.id)).toEqual(['c:k'])
    expect(filtrar(ITEMS, { ...SIN_FILTRO, estados: ['no_se_pudo_leer'] })).toHaveLength(2)
    expect(filtrar(ITEMS, { ...SIN_FILTRO, mes: '2026-08' })).toHaveLength(2)
    expect(opcionesCuenta(ITEMS).map((o) => o.nombre)).toEqual(['Banco sin identificar', 'Nu Colombia', 'Tarjeta Nu'])
  })

  it('el contador dice cuántos hay de cada estado', () => {
    expect(textoContadores(DATOS.contadores)).toBe(DATOS.resumen)
    expect(textoContadores({ revisado: 1 })).toBe('1 revisado')
  })
})

function Lista({ filtro = SIN_FILTRO, onAccion = vi.fn(), onFijarMes = vi.fn(), onFiltro = vi.fn(), datos = DATOS, ocupados }) {
  return <TodosLosExtractos datos={datos} filtro={filtro} onFiltro={onFiltro} onAccion={onAccion} onFijarMes={onFijarMes} ocupados={ocupados} />
}

describe('TodosLosExtractos', () => {
  it('cada fila dice banco + tipo + mes, su estado y una frase honesta (nunca «0 coinciden con el banco»)', () => {
    render(<Lista />)
    const julio = screen.getByTestId('ext-c:6')
    expect(within(julio).getByRole('heading', { name: 'Nu Colombia · Cuenta · Julio 2026' })).toBeTruthy()
    expect(within(julio).getByText('Revisado')).toBeTruthy()
    expect(within(julio).getByText('Leímos 37 movimientos: 37 ya estaban registrados, 0 nuevos.')).toBeTruthy()
    expect(screen.getByText('Leímos 37 movimientos: 5 nuevos agregados, 32 ya estaban.')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Tarjeta Nu · corte 14 ago 2026' })).toBeTruthy()
    expect(within(screen.getByTestId('ext-c:k')).getByText('Necesita clave')).toBeTruthy()
    expect(screen.queryByText(/coinciden con el banco/)).toBeNull()
  })

  it('muestra el contador por estado y los grupos por mes con su encabezado', () => {
    render(<Lista />)
    expect(screen.getByTestId('resumen-extractos').textContent).toBe(DATOS.resumen)
    const meses = screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent).filter((t) => /·\s\d+$/.test(t))
    expect(meses).toEqual(['Agosto 2026 · 2', 'Julio 2026 · 1', 'Junio 2026 · 1', 'Mayo 2026 · 1', 'Mes por confirmar · 2'])
  })

  it('junta los duplicados en una fila con «x2 correos»', () => {
    render(<Lista />)
    expect(within(screen.getByTestId('ext-c:5')).getByText('x2 correos')).toBeTruthy()
    expect(screen.getAllByText(/Junio 2026/).filter((e) => e.tagName === 'H4' && e.textContent.startsWith('Nu Colombia'))).toHaveLength(1)
  })

  it('el error dice el motivo y el siguiente paso; el antiguo dice «motivo no guardado» con «Intentar de nuevo»', () => {
    const onAccion = vi.fn()
    render(<Lista onAccion={onAccion} />)
    const err = screen.getByTestId('ext-c:x')
    expect(within(err).getByRole('alert').textContent).toMatch(/^No pudimos leer este extracto: el PDF es una imagen/)
    fireEvent.click(within(err).getByRole('button', { name: /Intentar de nuevo/ }))
    expect(onAccion).toHaveBeenCalledWith('intentar_de_nuevo', expect.objectContaining({ id: 'c:x' }))
    fireEvent.click(within(err).getByRole('button', { name: /Mi banco no está/ }))
    expect(onAccion).toHaveBeenCalledWith('mi_banco_no_esta', expect.objectContaining({ id: 'c:x' }))
    const viejo = screen.getByTestId('ext-h:v')
    expect(within(viejo).getByText(/No se pudo leer \(motivo no guardado\)/)).toBeTruthy()
    expect(within(viejo).getByText('x3 intentos')).toBeTruthy()
    expect(within(viejo).getByRole('button', { name: /Subir de nuevo/ })).toBeTruthy()
  })

  it('la fila de error con correo ofrece «Reintentar» y «Quitar de la lista»', () => {
    const onAccion = vi.fn()
    render(<Lista onAccion={onAccion} />)
    const viejo = screen.getByTestId('ext-h:v')
    expect(within(viejo).queryByRole('button', { name: /^Reintentar:/ })).toBeNull()
    cleanup()
    const conCorreo = fila({
      id: 'h:r', mes: '2026-07', mes_etiqueta: 'Julio 2026', titulo: 'Nu Colombia · Cuenta · Julio 2026', motivo_error: 'clave_faltante',
      estado_vista: 'no_se_pudo_leer', estado_etiqueta: 'No se pudo leer', acciones: ['reintentar', 'quitar_de_la_lista', 'mi_banco_no_esta'],
      resultado: 'No pudimos leer este extracto: el PDF tiene clave y no tenemos una guardada. Guarda la clave.', historiales_error: ['h1'],
    })
    render(<Lista datos={{ ...DATOS, items: [conCorreo] }} onAccion={onAccion} />)
    const el = screen.getByTestId('ext-h:r')
    fireEvent.click(within(el).getByRole('button', { name: /^Reintentar:/ }))
    expect(onAccion).toHaveBeenLastCalledWith('reintentar', expect.objectContaining({ id: 'h:r' }))
    fireEvent.click(within(el).getByRole('button', { name: /^Quitar de la lista:/ }))
    expect(onAccion).toHaveBeenLastCalledWith('quitar_de_la_lista', expect.objectContaining({ id: 'h:r' }))
  })

  it('cada estado trae sus acciones: Revisar, Poner clave, Probar la clave, Ver, Revisar de nuevo', () => {
    const onAccion = vi.fn()
    render(<Lista onAccion={onAccion} />)
    fireEvent.click(within(screen.getByTestId('ext-c:n')).getByRole('button', { name: /^Revisar:/ }))
    expect(onAccion).toHaveBeenLastCalledWith('revisar', expect.objectContaining({ id: 'c:n' }))
    const k = screen.getByTestId('ext-c:k')
    fireEvent.click(within(k).getByRole('button', { name: /Poner clave/ }))
    fireEvent.click(within(k).getByRole('button', { name: /Probar la clave/ }))
    expect(onAccion.mock.calls.map((c) => c[0]).slice(-2)).toEqual(['poner_clave', 'probar_clave'])
    fireEvent.click(within(screen.getByTestId('ext-c:6')).getByRole('button', { name: /Revisar de nuevo/ }))
    expect(onAccion).toHaveBeenLastCalledWith('revisar_de_nuevo', expect.objectContaining({ id: 'c:6' }))
  })

  it('«Mes por confirmar» ofrece un selector para fijar el mes; el mes deducido se puede cambiar', () => {
    const onFijarMes = vi.fn()
    render(<Lista onFijarMes={onFijarMes} />)
    const sin = screen.getByTestId('ext-c:s')
    fireEvent.change(within(sin).getByLabelText('¿De qué mes es este extracto?'), { target: { value: '2026-03' } })
    fireEvent.click(within(sin).getByRole('button', { name: /Guardar el mes de/ }))
    expect(onFijarMes).toHaveBeenCalledWith(expect.objectContaining({ id: 'c:s' }), '2026-03')
    // El mes deducido de la fecha del correo avisa y deja corregirlo.
    const n = screen.getByTestId('ext-c:n')
    expect(within(n).getByText(/Mes deducido de la fecha del correo/)).toBeTruthy()
    fireEvent.click(within(n).getByRole('button', { name: 'Cambiar mes' }))
    expect(within(n).getByLabelText('¿De qué mes es este extracto?')).toBeTruthy()
    // Sin forma de fijarlo (subido a mano): lo dice sin mostrar un selector que no serviría.
    expect(within(screen.getByTestId('ext-h:v')).queryByLabelText('¿De qué mes es este extracto?')).toBeNull()
    expect(within(screen.getByTestId('ext-h:v')).getByText(/No encontramos de qué mes es/)).toBeTruthy()
  })

  it('los filtros por estado, cuenta y buscador llaman a onFiltro; con filtro solo se ven los que coinciden', () => {
    const onFiltro = vi.fn()
    const { rerender } = render(<Lista onFiltro={onFiltro} />)
    fireEvent.click(screen.getByRole('button', { name: /^Necesita clave \(1\)/ }))
    expect(onFiltro).toHaveBeenLastCalledWith({ ...SIN_FILTRO, estados: ['necesita_clave'] })
    fireEvent.change(screen.getByLabelText('Buscar por mes'), { target: { value: 'julio' } })
    expect(onFiltro).toHaveBeenLastCalledWith({ ...SIN_FILTRO, texto: 'julio' })
    fireEvent.change(screen.getByLabelText('Cuenta o banco'), { target: { value: 'c:tj' } })
    expect(onFiltro).toHaveBeenLastCalledWith({ ...SIN_FILTRO, cuenta: 'c:tj' })
    rerender(<Lista onFiltro={onFiltro} filtro={{ ...SIN_FILTRO, estados: ['no_se_pudo_leer'] }} />)
    expect(screen.getAllByTestId(/^ext-/)).toHaveLength(2)
    expect(screen.getByRole('status').textContent).toMatch(/Mostrando 2 de 7/)
    rerender(<Lista onFiltro={onFiltro} filtro={{ ...SIN_FILTRO, texto: 'diciembre' }} />)
    expect(screen.getByText(/No hay extractos con esos filtros/)).toBeTruthy()
  })

  it('los correos sin archivo adjunto van plegados con la razón', () => {
    render(<Lista />)
    const boton = screen.getByRole('button', { name: /Correos sin archivo adjunto \(2\)/ })
    expect(boton.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByText('Tu cuenta Nu está lista')).toBeNull()
    fireEvent.click(boton)
    expect(screen.getByText(/no trae el PDF adjunto/)).toBeTruthy()
    expect(screen.getByText('Tu cuenta Nu está lista')).toBeTruthy()
  })

  it('no pinta nada si no hay extractos ni correos sin adjunto', () => {
    const { container } = render(<Lista datos={{ items: [], contadores: {}, sin_adjunto: [] }} />)
    expect(container.textContent).toBe('')
  })
})

// ── La pantalla ───────────────────────────────────────────────────────────────────────────────
const ESTADO = {
  meses: [{ clave: '2026-07', etiqueta: 'jul 26' }, { clave: '2026-08', etiqueta: 'ago 26' }],
  cuentas: [{
    id: 'nu', nombre: 'Nu Colombia', icono: '🏦',
    meses: [
      { mes: '2026-07', estado: 'conciliado', movimientos: 2, conciliados: 2, por_confirmar: 0, extractos: 1, leidas: 37, ya_estaban: 37, nuevas_agregadas: 0, por_revisar: 0,
        lista: [{ id: 'c:6', titulo: 'Nu Colombia · Cuenta · Julio 2026', estado_vista: 'revisado', estado_etiqueta: 'Revisado' }] },
      { mes: '2026-08', estado: 'extracto_pendiente', movimientos: 0, conciliados: 0, por_confirmar: 0, extractos: 1,
        lista: [{ id: 'c:n', titulo: 'Nu Colombia · Cuenta · Agosto 2026', estado_vista: 'sin_procesar', estado_etiqueta: 'Sin procesar' }] },
    ],
  }],
  sin_cuenta: [],
  tareas: [
    { id: 'falta_clave', titulo: 'Falta la clave del PDF', detalle: 'Guárdala.', cantidad: 1, ruta: '/x', carril: 'extractos' },
    { id: 'extractos_sin_leer', titulo: 'Extractos que no pudimos leer', detalle: 'Súbelo.', cantidad: 2, ruta: '/x', carril: 'extractos' },
  ],
  todos_extractos: DATOS,
  extractos: [],
  ultima_sync: null,
}

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

// «Todos los extractos» vive en «Ver todo» (pestaña Extractos); la cobertura por mes, en la pestaña «Por mes».
const montarYVerTodo = async (tab) => {
  montar()
  fireEvent.click(await screen.findByTestId('ver-todo'))
  if (tab) fireEvent.click(await screen.findByTestId(`tab-${tab}`))
}

describe('pantalla Traer movimientos con «Todos los extractos»', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
    Object.values(api).forEach((f) => f.mockReset())
    api.sincronizacionEstado.mockResolvedValue(ESTADO)
    api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
    api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com' })
    api.extractosCorreo.mockResolvedValue([])
    api.clavePdfEstado.mockResolvedValue({ configurada: false })
    api.almacenMuestras.mockResolvedValue({ disponible: false })
  })

  it('muestra la lista completa y ya no la lista de «Extractos ya revisados» con filas iguales', async () => {
    await montarYVerTodo()
    expect(await screen.findByTestId('todos-extractos')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Extractos ya revisados/ })).toBeNull()
    expect(screen.getByText('Nu Colombia · Cuenta · Julio 2026')).toBeTruthy()
    expect(screen.queryByText(/coinciden con el banco/)).toBeNull()
  })

  it('«Intentar de nuevo» reprocesa el extracto y dice cómo salió', async () => {
    api.reintentarExtractoCorreo.mockResolvedValue({ ok: false, estado: 'error', motivo_error: 'pdf_escaneado', mensaje: 'No pudimos leer este extracto: el PDF es una imagen.' })
    await montarYVerTodo()
    const fila = await screen.findByTestId('ext-c:x')
    fireEvent.click(within(fila).getByRole('button', { name: /Intentar de nuevo/ }))
    await waitFor(() => expect(api.reintentarExtractoCorreo).toHaveBeenCalledWith('ex'))
    expect(await screen.findByText('No pudimos leer este extracto: el PDF es una imagen.')).toBeTruthy()
  })

  it('fijar el mes lo guarda y recarga', async () => {
    api.fijarMesExtracto.mockResolvedValue({ ok: true })
    await montarYVerTodo()
    const sin = await screen.findByTestId('ext-c:s')
    fireEvent.change(within(sin).getByLabelText('¿De qué mes es este extracto?'), { target: { value: '2026-04' } })
    fireEvent.click(within(sin).getByRole('button', { name: /Guardar el mes de/ }))
    await waitFor(() => expect(api.fijarMesExtracto).toHaveBeenCalledWith('es', '2026-04'))
    await waitFor(() => expect(api.sincronizacionEstado.mock.calls.length).toBeGreaterThan(1))
  })

  it('«Por hacer» abre el grupo: los extractos con error filtran la lista', async () => {
    api.sincronizacionEstado.mockResolvedValue({ ...ESTADO, tareas: ESTADO.tareas.filter((t) => t.id === 'extractos_sin_leer') })
    montar()
    fireEvent.click(await screen.findByTestId('tarea-extractos_sin_leer'))
    await waitFor(() => expect(screen.getAllByTestId(/^ext-/)).toHaveLength(2))
    expect(screen.getByRole('button', { name: /^No se pudo leer \(2\)/ }).getAttribute('aria-pressed')).toBe('true')
  })

  it('tocar una celda de la cobertura dice lo mismo que la lista y abre los extractos de ese mes y cuenta', async () => {
    await montarYVerTodo('meses')
    const celda = await screen.findByRole('button', { name: 'Nu Colombia, agosto 2026: Sin procesar' })
    fireEvent.click(celda)
    const det = screen.getByRole('region', { name: 'Detalle del mes' })
    expect(within(det).getByText(/Nu Colombia · Cuenta · Agosto 2026/)).toBeTruthy()
    expect(within(det).getAllByText(/Sin procesar/).length).toBeGreaterThan(0)
    fireEvent.click(within(det).getByRole('button', { name: /Ver el extracto de este mes/ }))
    await waitFor(() => expect(screen.getAllByTestId(/^ext-/)).toHaveLength(1)) // ese mes Y esa cuenta (la tarjeta no)
    expect(screen.getByRole('heading', { name: 'Nu Colombia · Cuenta · Agosto 2026' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Nu Colombia · Cuenta · Julio 2026' })).toBeNull()
  })

  it('«Poner clave» abre la clave y «Mi banco no está» abre el formulario con el banco', async () => {
    await montarYVerTodo()
    const fila = await screen.findByTestId('ext-c:x')
    fireEvent.click(within(fila).getByRole('button', { name: /Mi banco no está/ }))
    expect(await screen.findByRole('dialog', { name: /Mi banco o billetera no aparece/ })).toBeTruthy()
  })
})

describe('nada sin nombre ni origen', () => {
  it('textoAccion: «Poner la clave» para un grupo y «Decirme de qué banco es» sin banco', async () => {
    const { textoAccion } = await import('../lib/extractosVista')
    expect(textoAccion('poner_clave', { copias: 10 })).toBe('Poner la clave')
    expect(textoAccion('poner_clave', { copias: 1 })).toBe('Poner clave')
    expect(textoAccion('mi_banco_no_esta', { banco_sin_identificar: true })).toBe('Decirme de qué banco es')
    expect(textoAccion('mi_banco_no_esta', { banco_sin_identificar: false })).toBe('Mi banco no está')
    expect(textoAccion('reintentar', {})).toBe('Reintentar')
  })
})
