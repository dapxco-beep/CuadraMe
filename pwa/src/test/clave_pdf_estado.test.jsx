// Clave del PDF: estado visible y confiable («Clave guardada ✓», cuántos extractos abrió, cuáles no),
// «Probar la clave ahora» y el resultado explícito. La clave nunca se muestra.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [{ id: 'c2', nombre: 'Bancolombia Ahorros', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: 'B' }]

const EXTRACTOS = [
  { id: 'e1', banco: 'Bancolombia', periodo: 'septiembre 2026', asunto: 'Extracto', archivo: 'a.pdf', estado: 'falta_clave', clave_estado: 'por_probar', cuenta_sugerida_id: 'c2', historial_id: null },
  { id: 'e2', banco: 'Davivienda', periodo: 'agosto 2026', asunto: 'Extracto', archivo: 'b.pdf', estado: 'falta_clave', clave_estado: 'no_abrio', cuenta_sugerida_id: null, historial_id: null },
]

const INFO = {
  configurada: true, cantidad_claves: 1, protegidos: 2, abrieron: 0, no_abrieron: 1, por_probar: 1,
  por_banco: [
    { banco: 'Bancolombia', protegidos: 1, abrieron: 0, no_abrieron: 0, por_probar: 1 },
    { banco: 'Davivienda', protegidos: 1, abrieron: 0, no_abrieron: 1, por_probar: 0 },
  ],
  extractos: [
    { id: 'e1', nombre: 'Bancolombia septiembre 2026', banco: 'Bancolombia', resultado: 'por_probar', estado: 'falta_clave' },
    { id: 'e2', nombre: 'Davivienda agosto 2026', banco: 'Davivienda', resultado: 'no_abrio', estado: 'falta_clave' },
  ],
}

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  guardarClavePdf: vi.fn(),
  borrarClavePdf: vi.fn(),
  probarClavePdf: vi.fn(),
  sincronizarCorreos: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ nombres: ['Otros'], iconoDe: () => '' }) }))

import { DialogosProvider } from '../lib/DialogosContext'
import Sincronizacion from '../screens/Sincronizacion'
import EstadoClavePdf, { textoEstadoClave } from '../components/EstadoClavePdf'

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

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('cuadrame_gmail_sync', String(Date.now())) // sin sincronización automática
  Object.values(api).forEach((f) => f.mockReset())
  api.sincronizacionEstado.mockResolvedValue({
    meses: [], cuentas: [], sin_cuenta: [], ultima_sync: null,
    tareas: [{ id: 'falta_clave', titulo: 'Falta la clave del PDF', detalle: '', cantidad: 2, ruta: '/sincronizacion#clave' }],
    punto_partida: { definido: true, modo: 'hoy', fecha: '2026-10-01', anteriores: { correos: 0, extractos: 0 } },
  })
  api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com', etiqueta: 'gastos' })
  api.correosPendientes.mockResolvedValue([])
  api.extractosCorreo.mockResolvedValue(EXTRACTOS)
  api.clavePdfEstado.mockResolvedValue(INFO)
})

describe('EstadoClavePdf (componente)', () => {
  it('dice si hay clave guardada y nunca la muestra', () => {
    expect(textoEstadoClave({ configurada: true })).toBe('Clave guardada ✓')
    expect(textoEstadoClave({ configurada: true, cantidad_claves: 2 })).toBe('Clave guardada ✓ (2 claves)')
    expect(textoEstadoClave({ configurada: false })).toBe('Sin clave guardada')
    render(<EstadoClavePdf info={INFO} onGuardar={vi.fn()} onBorrar={vi.fn()} onProbar={vi.fn()} />)
    expect(screen.getByTestId('clave-estado')).toHaveTextContent('Clave guardada ✓')
    expect(screen.getByLabelText('Clave del PDF').type).toBe('password')
    expect(screen.getByTestId('clave-resumen')).toHaveTextContent('2 extractos protegidos · abrió 0 · no abrió 1 · por probar 1')
  })

  it('lista por extracto qué pasó, en lenguaje llano', () => {
    render(<EstadoClavePdf info={INFO} onGuardar={vi.fn()} onBorrar={vi.fn()} onProbar={vi.fn()} />)
    const lista = screen.getByRole('list', { name: 'Resultado por extracto' })
    expect(within(lista).getByText(/Davivienda agosto 2026/).closest('li')).toHaveTextContent('La clave no lo abrió: revísala')
    expect(within(lista).getByText(/Bancolombia septiembre 2026/).closest('li')).toHaveTextContent('Por probar')
  })

  it('«Probar la clave ahora» muestra el resultado de la prueba', () => {
    const onProbar = vi.fn()
    render(
      <EstadoClavePdf
        info={INFO} onGuardar={vi.fn()} onBorrar={vi.fn()} onProbar={onProbar}
        resultado={{ abrieron: 1, no_abrieron: 1 }}
        mensaje="La clave funcionó en 1 extracto. Esta clave no abrió el extracto Davivienda agosto 2026: revísala."
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /Probar la clave ahora|Volver a probar la clave/ }))
    expect(onProbar).toHaveBeenCalled()
    expect(screen.getByTestId('clave-resultado')).toHaveTextContent('La clave funcionó en 1 extracto.')
    expect(screen.getByTestId('clave-resultado')).toHaveTextContent('no abrió el extracto Davivienda agosto 2026: revísala')
  })
})

describe('Traer movimientos: clave del PDF', () => {
  it('muestra el estado, y «Probar la clave ahora» llama al servidor y dice cuántos abrió', async () => {
    api.probarClavePdf.mockResolvedValue({
      ok: true, abrieron: 1, no_abrieron: 1, restantes: 0,
      mensaje: 'La clave funcionó en 1 extracto. Esta clave no abrió el extracto Davivienda agosto 2026: revísala.',
    })
    montar()
    fireEvent.click(await screen.findByTestId('tarea-falta_clave')) // el paso «Falta la clave» abre su hoja
    const caja = await screen.findByTestId('estado-clave-pdf')
    expect(within(caja).getByTestId('clave-estado')).toHaveTextContent('Clave guardada ✓')
    fireEvent.click(within(caja).getByRole('button', { name: /Probar la clave ahora/ }))
    await waitFor(() => expect(api.probarClavePdf).toHaveBeenCalledWith(undefined))
    expect(await screen.findByTestId('clave-resultado')).toHaveTextContent('La clave funcionó en 1 extracto.')
    // y vuelve a pedir el estado para reflejarlo
    await waitFor(() => expect(api.clavePdfEstado.mock.calls.length).toBeGreaterThan(1))
  })

  it('cada extracto protegido dice si la clave lo abrió y permite probarla solo en ese', async () => {
    api.probarClavePdf.mockResolvedValue({ ok: true, abrieron: 1, no_abrieron: 0, restantes: 0, mensaje: 'La clave funcionó en 1 extracto.' })
    montar()
    fireEvent.click(await screen.findByTestId('ver-todo')) // la lista de extractos está en «Ver todo»
    const noAbrio = await screen.findByTestId('extracto-e2')
    expect(within(noAbrio).getByTestId('clave-no-abrio')).toHaveTextContent('La clave guardada no abrió este extracto: revísala.')
    const porProbar = screen.getByTestId('extracto-e1')
    expect(within(porProbar).getByText('Falta probar la clave en este extracto.')).toBeInTheDocument()
    fireEvent.click(within(porProbar).getByRole('button', { name: 'Probar la clave ahora' }))
    await waitFor(() => expect(api.probarClavePdf).toHaveBeenCalledWith('e1'))
  })

  it('al guardar una clave nueva con extractos esperando, la prueba de una vez', async () => {
    api.clavePdfEstado.mockResolvedValue({ ...INFO, configurada: false, cantidad_claves: 0 })
    api.guardarClavePdf.mockResolvedValue({ ok: true, configurada: true })
    api.probarClavePdf.mockResolvedValue({ ok: true, abrieron: 2, no_abrieron: 0, restantes: 0, mensaje: 'La clave funcionó en 2 extractos.' })
    montar()
    fireEvent.click(await screen.findByTestId('tarea-falta_clave')) // el paso «Falta la clave» abre su hoja
    const caja = await screen.findByTestId('estado-clave-pdf')
    expect(within(caja).getByTestId('clave-estado')).toHaveTextContent('Sin clave guardada')
    fireEvent.change(within(caja).getByLabelText('Clave del PDF'), { target: { value: '1020304050' } })
    fireEvent.click(within(caja).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(api.guardarClavePdf).toHaveBeenCalledWith('1020304050'))
    await waitFor(() => expect(api.probarClavePdf).toHaveBeenCalled())
    expect(await screen.findByText('La clave funcionó en 2 extractos.')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('1020304050')).toBeNull()
  })
})
