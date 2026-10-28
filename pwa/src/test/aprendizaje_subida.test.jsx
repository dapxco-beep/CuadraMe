// Aprendizaje de categorías (huella de comercio, «Recordar», Entrenar categorías) y
// subida múltiple de extractos (cola con un archivo fallido, deduplicación entre archivos).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  vocabularioCategorias: vi.fn(),
  aprenderRegla: vi.fn(),
  explicarCategoria: vi.fn(),
  obtenerReviewExtracto: vi.fn(),
  procesarExtracto: vi.fn(),
  importarFaltantes: vi.fn(),
  importarVistaPrevia: vi.fn(),
  importarConfirmar: vi.fn(),
  clavePdfEstado: vi.fn(),
  guardarClavePdf: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({
    cuentas: [{ id: 'c1', nombre: 'Nequi', icono: '💜' }, { id: 'c2', nombre: 'Bancolombia', icono: '🏦' }],
    recargar: vi.fn(),
  }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Hogar', 'Ocio', 'Otros'], iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { claveComercio, huellaPeligrosa } from '../lib/comercio'
import { construirFilas } from '../lib/importar'
import {
  MAX_ARCHIVOS,
  claveDedup,
  clavesFaltantes,
  consolidar,
  fechaISO,
  normalizarPdf,
  normalizarTabular,
  procesarCola,
  sugerirCuenta,
  tipoDeArchivo,
  validarSeleccion,
} from '../lib/subidaMultiple'
import EntrenarCategorias, { textoProgreso } from '../screens/EntrenarCategorias'
import SubidaMultiple from '../components/SubidaMultiple'

const montar = (ui, estado) =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={[{ pathname: '/', state: estado }]}>{ui}</MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

describe('huella de comercio (misma que el servidor)', () => {
  it.each([
    ['PAGO EN VENTO COLIVING 0105', 'vento coliving'],
    ['COMPRA VENTO COLIVING BOGOTA', 'vento coliving'],
    ['COMPRA EN JUAN VALDEZ SKANDIA CON TARJETA DEBITO', 'juan valdez skandia'],
    ['PAGO PSE CLARO COLOMBIA S.A.S.', 'claro'],
    ["COMPRA EN PAN PA' YA BOGOTA CO", 'pan pa ya'],
    ['D1 SUC 4521 MEDELLIN', 'd1'],
    ['COMPRA MERCADO LIBRE COLOMBIA 123456789', 'mercado libre'],
    ['Compra en EXITO CHAPINERO 12/03/2025', 'exito chapinero'],
    ['COMPRA EN PANADERÍA LA ESPIGA REF 4455', 'panaderia la espiga'],
    ['TRANSFERENCIA A NEQUI JUAN PEREZ', 'juan perez'],
  ])('%s -> %s', (desc, esperada) => {
    expect(claveComercio(desc)).toBe(esperada)
  })

  it('marca como peligrosas las huellas demasiado amplias', () => {
    expect(huellaPeligrosa('d1')).toMatch(/demasiado corta/)
    expect(huellaPeligrosa('pago')).toMatch(/genérica/)
    expect(huellaPeligrosa('')).toBeTruthy()
    expect(huellaPeligrosa('vento coliving')).toBeNull()
  })

  it('construirFilas envía recordar solo en las filas con «Recordar» marcado', () => {
    const propuesta = [
      { fila: 1, fecha: '2025-10-01', descripcion: 'A', monto: 5, tipo: 'expense', estado: 'nuevo' },
      { fila: 2, fecha: '2025-10-02', descripcion: 'B', monto: 6, tipo: 'expense', estado: 'nuevo' },
    ]
    const filas = construirFilas(propuesta, new Set([1, 2]), { 1: 'Hogar', 2: 'Ocio' }, { 1: { recordar: true, anteriores: true } })
    expect(filas[0]).toMatchObject({ categoria: 'Hogar', recordar: true, aplicar_anteriores: true })
    expect(filas[1]).not.toHaveProperty('recordar')
  })
})

describe('Entrenar categorías', () => {
  const vocab = {
    progreso: { reglas: 3, comercios_entrenados: 12, movimientos: 100, con_categoria: 83, porcentaje: 83, pendientes_comercios: 2 },
    comercios: [
      { clave: 'vento coliving', tipo: 'comercio', conteo: 3, monto_total: 2700000, ejemplo: 'PAGO EN VENTO COLIVING 0105', categoria_actual: 'Otros', peligrosa: null, movimiento_id: 'm1' },
    ],
    palabras: [{ clave: 'pan', tipo: 'palabra', conteo: 4, monto_total: 80000, ejemplo: 'COMPRA PAN TIENDA', categoria_actual: 'Otros', peligrosa: '«pan» es demasiado corta y podría coincidir con muchos comercios' }],
  }

  it('muestra el progreso y guarda la regla con «aplicar a anteriores»', async () => {
    api.vocabularioCategorias.mockResolvedValue(vocab)
    api.aprenderRegla.mockResolvedValue({ guardada: true, huella: 'vento coliving', anteriores_actualizados: 2 })
    montar(<EntrenarCategorias />)
    expect(await screen.findByText('Entrenaste 12 comercios · 83 % de tus movimientos ya tienen categoría')).toBeInTheDocument()
    expect(textoProgreso({ comercios_entrenados: 1, porcentaje: 50 })).toBe('Entrenaste 1 comercio · 50 % de tus movimientos ya tienen categoría')

    const fila = screen.getAllByTestId('fila-entrenar')[0]
    await userEvent.selectOptions(within(fila).getByLabelText('Categoría para vento coliving'), 'Hogar')
    await userEvent.click(within(fila).getByRole('button', { name: /Guardar regla/ }))
    await waitFor(() =>
      expect(api.aprenderRegla).toHaveBeenCalledWith({
        descripcion: 'PAGO EN VENTO COLIVING 0105', categoria: 'Hogar', aplicar_anteriores: true, confirmar_peligrosa: false,
      })
    )
    expect(await screen.findByText(/Corregí 2 movimientos anteriores/)).toBeInTheDocument()
    expect(api.vocabularioCategorias).toHaveBeenCalledTimes(2) // recarga el progreso
  })

  it('una palabra peligrosa pide marcar la casilla para guardarse', async () => {
    api.vocabularioCategorias.mockResolvedValue(vocab)
    api.aprenderRegla.mockResolvedValue({ guardada: true, huella: 'pan', anteriores_actualizados: 0 })
    montar(<EntrenarCategorias />)
    const filas = await screen.findAllByTestId('fila-entrenar')
    const pan = filas[1]
    await userEvent.selectOptions(within(pan).getByLabelText('Categoría para pan'), 'Comida')
    await userEvent.click(within(pan).getByLabelText(/Marca esta casilla|demasiado corta/))
    await userEvent.click(within(pan).getByRole('button', { name: /Guardar regla/ }))
    await waitFor(() =>
      expect(api.aprenderRegla).toHaveBeenCalledWith(expect.objectContaining({ descripcion: 'pan', confirmar_peligrosa: true }))
    )
  })

  it('"¿Por qué se categorizó así?" muestra la razón', async () => {
    api.vocabularioCategorias.mockResolvedValue(vocab)
    api.explicarCategoria.mockResolvedValue({
      resultados: [{ descripcion: 'COMPRA PANADERIA LA ESPIGA', huella: 'panaderia la espiga', categoria_guardada: 'Otros', categoria_sugerida: 'Comida', razon: 'por palabra clave «panaderia»', es_ejemplo: false }],
    })
    montar(<EntrenarCategorias />)
    await userEvent.type(await screen.findByLabelText('Buscar un movimiento de ejemplo'), 'espiga')
    await userEvent.click(screen.getByRole('button', { name: 'Buscar' }))
    expect(await screen.findByText('por palabra clave «panaderia»')).toBeInTheDocument()
    expect(api.explicarCategoria).toHaveBeenCalledWith('espiga')
  })

  it('sin pendientes muestra un estado vacío', async () => {
    api.vocabularioCategorias.mockResolvedValue({ progreso: { ...vocab.progreso, porcentaje: 100 }, comercios: [], palabras: [] })
    montar(<EntrenarCategorias />)
    expect(await screen.findByText('No hay nada por enseñar')).toBeInTheDocument()
  })
})

describe('Revisión: «Recordar» al corregir la categoría', () => {
  it('al cambiar la categoría aparece «Recordar para …» marcado y se envía al importar', async () => {
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h1', exactos: 0, aproximados: 0, faltantes: 1, completados: 0, sobrantes: 0, total_movimientos: 1, descartados: 0,
      review: [{ fingerprint: 'fp1', fecha: '2026-10-03', descripcion: 'PAGO EN VENTO COLIVING 0105', monto: 900000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Otros' }],
    })
    api.importarFaltantes.mockResolvedValue({ ok: true, importados: 1, sin_categoria_clara: 0, categorizados_auto: 0, reglas_guardadas: 1 })
    montar(<SubidaMultiple revisionInicial={{ historialId: 'h1' }} />)
    const select = await screen.findByLabelText('Categoría de PAGO EN VENTO COLIVING 0105')
    expect(screen.queryByText(/Recordar para/)).toBeNull() // sin editar, no se ofrece
    await userEvent.selectOptions(select, 'Hogar')
    const casilla = await screen.findByRole('checkbox', { name: /Recordar para «vento coliving»/ })
    expect(casilla).toBeChecked()
    await userEvent.click(screen.getByRole('checkbox', { name: /Aplicar también a los anteriores/ }))
    await userEvent.click(screen.getByRole('button', { name: /Importar \(1\)/ }))
    await waitFor(() =>
      expect(api.importarFaltantes).toHaveBeenCalledWith('h1', ['fp1'], { fp1: 'Hogar' }, { recordar: ['fp1'], aplicar_anteriores: ['fp1'] })
    )
  })
})

describe('subida múltiple: lógica', () => {
  const f = (nombre, size = 1000) => ({ name: nombre, size })

  it('reconoce formatos y limita a 10 archivos con motivo legible', () => {
    expect(tipoDeArchivo('Extracto.PDF')).toBe('pdf')
    expect(tipoDeArchivo('mov.xlsx')).toBe('tabular')
    expect(tipoDeArchivo('foto.png')).toBeNull()
    const doce = Array.from({ length: 12 }, (_, i) => f(`e${i}.pdf`))
    const r = validarSeleccion([...doce, f('foto.png'), f('grande.pdf', 20 * 1024 * 1024)])
    expect(r.aceptados).toHaveLength(MAX_ARCHIVOS)
    expect(r.rechazados.map((x) => x.motivo).join(' ')).toMatch(/Formato no soportado/)
    expect(r.rechazados.find((x) => x.nombre === 'grande.pdf').motivo).toMatch(/15 MB/)
    expect(r.rechazados.filter((x) => /Máximo 10/.test(x.motivo))).toHaveLength(2) // los 2 PDF que pasan del tope
  })

  it('sugiere la cuenta por el nombre del archivo', () => {
    const cuentas = [{ id: 'c1', nombre: 'Nequi' }, { id: 'c2', nombre: 'Bancolombia' }]
    expect(sugerirCuenta('extracto_bancolombia_sep.pdf', cuentas, 'c1')).toBe('c2')
    expect(sugerirCuenta('extracto.pdf', cuentas, 'c1')).toBe('c1')
  })

  it('un archivo que falla no detiene a los demás', async () => {
    const archivos = ['a', 'b', 'c'].map((id) => ({ id, nombre: `${id}.pdf`, estado: 'pendiente' }))
    const cambios = []
    const progreso = []
    await procesarCola(
      archivos,
      async (a) => {
        if (a.id === 'b') throw new Error('PDF dañado')
        return { estado: a.id === 'c' ? 'falta_clave' : 'listo' }
      },
      { onCambio: (id, p) => cambios.push([id, p.estado, p.error]), onProgreso: (p) => progreso.push(p.actual) }
    )
    expect(cambios).toEqual([
      ['a', 'procesando', ''], ['a', 'listo', undefined],
      ['b', 'procesando', ''], ['b', 'error', 'PDF dañado'],
      ['c', 'procesando', ''], ['c', 'falta_clave', undefined],
    ])
    expect(progreso.slice(0, 3)).toEqual([1, 2, 3])
  })

  it('fechas y claves de deduplicación', () => {
    expect(fechaISO('03/10/2026')).toBe('2026-10-03')
    expect(fechaISO('2026-10-3')).toBe('2026-10-03')
    expect(claveDedup('c1', { fecha: '03/10/2026', monto: 900000, tipo: 'expense', descripcion: 'PAGO EN VENTO COLIVING 0105' })).toBe(
      claveDedup('c1', { fecha: '2026-10-03', monto: 900000, tipo: 'expense', descripcion: 'COMPRA VENTO COLIVING BOGOTA' })
    )
  })

  it('periodos solapados: el mismo movimiento en dos extractos se cuenta una sola vez', () => {
    const mov = (extra) => ({ fecha: '2026-10-03', monto: 900000, tipo: 'expense', descripcion: 'PAGO EN VENTO COLIVING 0105', ...extra })
    const a1 = { id: 'a1', nombre: 'sep.pdf', estado: 'listo', cuentaId: 'c1', items: [{ k: 'x', estado: 'nuevo', ...mov() }, { k: 'y', estado: 'nuevo', ...mov({ descripcion: 'EXITO', monto: 5000 }) }] }
    const a2 = { id: 'a2', nombre: 'sep-oct.pdf', estado: 'listo', cuentaId: 'c1', items: [{ k: 'z', estado: 'nuevo', ...mov({ descripcion: 'COMPRA VENTO COLIVING BOGOTA' }) }] }
    const a3 = { id: 'a3', nombre: 'otra-cuenta.pdf', estado: 'listo', cuentaId: 'c2', items: [{ k: 'w', estado: 'nuevo', ...mov() }] }
    const { archivos, repetidos } = consolidar([a1, a2, a3])
    expect(repetidos).toBe(1)
    expect(archivos[1].items[0]).toMatchObject({ estado: 'repetido', repetidoDe: 'sep.pdf' })
    expect(archivos[2].items[0].estado).toBe('nuevo') // otra cuenta: no es duplicado
    expect(clavesFaltantes(archivos)).toEqual(['a1:x', 'a1:y', 'a3:w'])
  })

  it('normaliza la respuesta del PDF y del Excel/CSV', () => {
    const pdf = normalizarPdf({
      historial_id: 'h', banco_detectado: 'nequi', periodo_desde: '2026-09-01', periodo_hasta: '2026-09-30',
      review: [
        { fingerprint: 'f1', fecha: '2026-09-02', descripcion: 'A', monto: 1, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Comida', razon_categoria: 'por palabra clave «pan»' },
        { fingerprint: 'f2', fecha: '2026-09-03', descripcion: 'B', monto: 2, tipo: 'expense', estado: 'exacto' },
        { fingerprint: 's', fecha: '2026-09-03', descripcion: 'C', monto: 3, tipo: 'expense', estado: 'sobrante' },
      ],
    })
    expect(pdf.items.map((i) => [i.k, i.estado])).toEqual([['f1', 'nuevo'], ['f2', 'ya']])
    expect(pdf.periodo).toEqual({ desde: '2026-09-01', hasta: '2026-09-30' })
    const tab = normalizarTabular({
      propuesta: [
        { fila: 2, fecha: '2026-09-05', descripcion: 'X', monto: 5, tipo: 'income', categoria: 'Ingresos', estado: 'nuevo' },
        { fila: 3, fecha: '2026-09-09', descripcion: 'Y', monto: 6, tipo: 'expense', categoria: 'Otros', estado: 'posible_duplicado' },
      ],
    })
    expect(tab.items.map((i) => i.estado)).toEqual(['nuevo', 'posible'])
    expect(tab.periodo).toEqual({ desde: '2026-09-05', hasta: '2026-09-09' })
  })
})

describe('subida múltiple: pantalla', () => {
  const pdf = (nombre) => new File(['%PDF-1.4'], nombre, { type: 'application/pdf' })
  const respuesta = (desc) => ({
    ok: true, historial_id: `h-${desc}`, banco_detectado: 'nequi', total_movimientos: 1, periodo_desde: '2026-09-01', periodo_hasta: '2026-09-30',
    review: [{ fingerprint: `fp-${desc}`, fecha: '2026-09-03', descripcion: desc, monto: 9000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Otros' }],
  })

  it('la clave que abre el PDF se guarda (cifrada) para los próximos extractos, si no había ninguna', async () => {
    api.clavePdfEstado.mockResolvedValue({ configurada: false })
    api.guardarClavePdf.mockResolvedValue({ ok: true })
    api.procesarExtracto
      .mockResolvedValueOnce({ ok: false, requiere_clave: true, error: 'El PDF tiene clave' })
      .mockResolvedValueOnce(respuesta('CAFE CLAVE'))
    montar(<SubidaMultiple archivosIniciales={[pdf('con-clave.pdf')]} cuentaInicial="c1" onCancelar={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Procesar/ }))
    const campo = await screen.findByLabelText('Clave de con-clave.pdf')
    expect(await screen.findByLabelText(/Guardar esta clave/)).toBeChecked()
    await userEvent.type(campo, '1234')
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText(/Clave guardada: tus próximos extractos se abren solos/)).toBeInTheDocument()
    expect(api.guardarClavePdf).toHaveBeenCalledWith('1234')
  })

  it('si la persona desmarca la casilla, la clave NO se guarda', async () => {
    api.clavePdfEstado.mockResolvedValue({ configurada: false })
    api.procesarExtracto
      .mockResolvedValueOnce({ ok: false, requiere_clave: true, error: 'El PDF tiene clave' })
      .mockResolvedValueOnce(respuesta('CAFE SOLO UNA VEZ'))
    montar(<SubidaMultiple archivosIniciales={[pdf('una-vez.pdf')]} cuentaInicial="c1" onCancelar={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Procesar/ }))
    await userEvent.click(await screen.findByLabelText(/Guardar esta clave/))
    await userEvent.type(screen.getByLabelText('Clave de una-vez.pdf'), 'abcd')
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    await waitFor(() => expect(api.procesarExtracto).toHaveBeenCalledTimes(2))
    expect(api.guardarClavePdf).not.toHaveBeenCalled()
  })

  it('si ya hay una clave guardada no ofrece guardar otra (no se pisa la de los demás PDF)', async () => {
    api.clavePdfEstado.mockResolvedValue({ configurada: true })
    api.procesarExtracto.mockResolvedValueOnce({ ok: false, requiere_clave: true, error: 'El PDF tiene clave' })
    montar(<SubidaMultiple archivosIniciales={[pdf('otro-banco.pdf')]} cuentaInicial="c1" onCancelar={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Procesar/ }))
    await screen.findByLabelText('Clave de otro-banco.pdf')
    expect(screen.queryByLabelText(/Guardar esta clave/)).toBeNull()
  })

  it('procesa en cola, muestra el estado de cada archivo y deja revisar los que salieron bien', async () => {
    api.procesarExtracto
      .mockResolvedValueOnce(respuesta('CAFE UNO'))
      .mockResolvedValueOnce({ ok: false, requiere_clave: true, error: 'El PDF tiene clave: escríbela e inténtalo de nuevo.' })
      .mockResolvedValueOnce(respuesta('CAFE TRES'))
    api.importarFaltantes.mockResolvedValue({ ok: true, importados: 1, duplicados_omitidos: 0 })
    montar(<SubidaMultiple archivosIniciales={[pdf('uno.pdf'), pdf('dos.pdf'), pdf('tres.pdf')]} cuentaInicial="c1" onCancelar={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: /Procesar 3 archivos/ }))
    expect(await screen.findByText('Falta la clave del PDF')).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByText('Listo')).toHaveLength(2))
    expect(api.procesarExtracto).toHaveBeenCalledTimes(3) // el de la clave no frenó al tercero
    expect(screen.getByLabelText('Clave de dos.pdf')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Revisar \(2 archivos\)/ }))
    expect(await screen.findByTestId('revision-multiple')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Seleccionar todo lo que falta \(2\)/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Importar \(2\)/ }))
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalledTimes(2))
    expect(api.importarFaltantes).toHaveBeenCalledWith('h-CAFE UNO', ['fp-CAFE UNO'], { 'fp-CAFE UNO': 'Otros' }, { recordar: [], aplicar_anteriores: [] })
    expect(await screen.findByTestId('resultado-multiple')).toBeInTheDocument()
  })

  it('un error del servidor se muestra con motivo legible y no bloquea el resto', async () => {
    api.procesarExtracto
      .mockRejectedValueOnce(new Error('Servidor ocupado'))
      .mockResolvedValueOnce(respuesta('CAFE DOS'))
    montar(<SubidaMultiple archivosIniciales={[pdf('a.pdf'), pdf('b.pdf')]} cuentaInicial="c1" onCancelar={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Procesar 2 archivos/ }))
    expect(await screen.findByText('Servidor ocupado')).toBeInTheDocument()
    expect(await screen.findByText('No se pudo procesar')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Listo')).toBeInTheDocument())
  })

  it('dos extractos con el mismo movimiento solo importan una vez', async () => {
    api.procesarExtracto.mockResolvedValueOnce(respuesta('CAFE IGUAL')).mockResolvedValueOnce({
      ...respuesta('CAFE IGUAL'), historial_id: 'h-otro',
      review: [{ fingerprint: 'fp-otro', fecha: '2026-09-03', descripcion: 'CAFE IGUAL', monto: 9000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Otros' }],
    })
    api.importarFaltantes.mockResolvedValue({ ok: true, importados: 1 })
    montar(<SubidaMultiple archivosIniciales={[pdf('a.pdf'), pdf('b.pdf')]} cuentaInicial="c1" onCancelar={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Procesar 2 archivos/ }))
    await userEvent.click(await screen.findByRole('button', { name: /Revisar \(2 archivos\)/ }))
    expect(await screen.findByText(/Ya está en a\.pdf/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Importar \(1\)/ }))
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalledTimes(1))
  })
})
