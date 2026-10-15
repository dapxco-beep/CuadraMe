import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const GRUPOS = [
  { huella: 'clinica norte', nombre: 'clinica norte', conteo: 1, monto_total: 900000, ejemplo: 'Compra CLINICA NORTE', movimiento_id: 'm9', movimiento_ids: ['m9'], categoria_actual: 'Otros', motivos: ['otros'], relevante: true },
  { huella: 'kopi zebra', nombre: 'kopi zebra', conteo: 3, monto_total: 15000, ejemplo: 'Compra KOPI ZEBRA', movimiento_id: 'm1', movimiento_ids: ['m1', 'm2', 'm3'], categoria_actual: 'Otros', motivos: ['otros'], relevante: true },
  { huella: 'tienda rara', nombre: 'tienda rara', conteo: 1, monto_total: 2000, ejemplo: 'Compra TIENDA RARA', movimiento_id: 'm7', movimiento_ids: ['m7'], categoria_actual: 'Otros', motivos: ['otros'], relevante: false },
]
const RESUMEN = {
  conteo: { total: 5, otros: 5, baja: 0, marcadas: 0, silenciados: 0 },
  total_grupos: 3, relevantes: 2, monto_total: 917000, peso_relevantes: 99, grupos: GRUPOS, hay_mas: false,
}

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({
    categorias: [], activas: [], nombres: ['Comida', 'Ocio'], cargando: false, recargar: vi.fn(),
    iconoDe: () => '💳', colorDe: () => null,
  }),
}))

import PorCategorizar from '../screens/PorCategorizar'
import {
  alternarComercio, alternarMovimiento, contarSeleccion, cuerpoAccion, loQueMasPesa, ninguno,
  recordarPorDefecto, seleccionarVisibles, textoVistaPrevia,
} from '../lib/porCategorizar'
import { porRevisar } from '../lib/comercio'

function montar() {
  return render(
    <MemoryRouter>
      <PorCategorizar />
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    porCategorizar: vi.fn().mockResolvedValue(RESUMEN),
    silenciosPorCategorizar: vi.fn().mockResolvedValue({ silencios: [] }),
    accionPorCategorizar: vi.fn().mockResolvedValue({ ok: true, movimientos: 3, previos: [{ id: 'm1' }], huellas_nuevas: ['kopi zebra'], huellas: ['kopi zebra'] }),
    deshacerPorCategorizar: vi.fn().mockResolvedValue({ ok: true }),
    quitarSilencios: vi.fn().mockResolvedValue({ ok: true }),
    movimientos: vi.fn().mockResolvedValue([]),
    similaresConteo: vi.fn().mockResolvedValue({ conteo: 2 }),
  })
})

describe('lógica de selección (pura)', () => {
  it('selecciona por comercio, por movimiento y cuenta sin duplicar', () => {
    let s = alternarComercio(ninguno(), 'kopi zebra')
    s = alternarMovimiento(s, 'm1') // ya cubierto por el comercio
    s = alternarMovimiento(s, 'm9')
    expect(contarSeleccion(s, GRUPOS)).toBe(3 + 1)
    expect(contarSeleccion(alternarComercio(s, 'kopi zebra'), GRUPOS)).toBe(2) // quedan m1 y m9 sueltos
  })
  it('seleccionar los visibles y ninguno', () => {
    expect(seleccionarVisibles(GRUPOS).huellas.size).toBe(3)
    expect(ninguno().huellas.size).toBe(0)
  })
  it('arma el cuerpo de la acción', () => {
    const b = cuerpoAccion('dejar', alternarComercio(ninguno(), 'kopi zebra'))
    expect(b).toEqual({ accion: 'dejar', huellas: ['kopi zebra'], movimiento_ids: [] })
  })
  it('lo que más pesa: relevantes primero, con tope', () => {
    expect(loQueMasPesa(GRUPOS, 5).map((g) => g.huella)).toEqual(['clinica norte', 'kopi zebra'])
    expect(loQueMasPesa([GRUPOS[2]]).length).toBe(1)
  })
  it('recordar viene activado solo desde 4 repeticiones', () => {
    expect(recordarPorDefecto(1)).toBe(false)
    expect(recordarPorDefecto(3)).toBe(false)
    expect(recordarPorDefecto(4)).toBe(true)
    expect(textoVistaPrevia(12)).toBe('Afectará 12 movimientos pasados y los futuros.')
  })
  it('por categorizar: usa el flag del servidor y, si falta, la misma regla', () => {
    expect(porRevisar({ por_categorizar: false, categoria: 'Otros' })).toBe(false)
    expect(porRevisar({ categoria: 'Otros', cat_confirmada: true })).toBe(true)
    expect(porRevisar({ categoria: 'Comida', cat_confirmada: false, cat_origen: 'regla' })).toBe(false)
    expect(porRevisar({ categoria: 'Comida', cat_confirmada: false, cat_origen: 'sugerida' })).toBe(true)
    expect(porRevisar({ categoria: 'Comida', cat_confirmada: true, cat_origen: 'marcada' })).toBe(true)
    expect(porRevisar({ categoria: 'Otros', cat_origen: 'dejada' })).toBe(false)
    expect(porRevisar({ categoria: 'Otros', fuente: 'transferencia_interna' })).toBe(false)
  })
})

describe('pantalla Por categorizar', () => {
  it('muestra el mensaje de ritmo y los comercios con casillas etiquetadas', async () => {
    montar()
    expect(await screen.findByText(/Lo importante son los comercios que se repiten o pesan/)).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /Seleccionar kopi zebra, 3 movimientos/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Categorizar lo que más pesa en 1 minuto/ })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: /Acciones sobre lo seleccionado/ })).toBeNull() // nada obligatorio
  })

  it('seleccionar un comercio muestra las acciones y «No volver a preguntar» se puede deshacer', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('checkbox', { name: /Seleccionar kopi zebra/ }))
    const barra = screen.getByRole('region', { name: /Acciones sobre lo seleccionado/ })
    expect(within(barra).getByText(/Seleccionaste 3 movimientos/)).toBeInTheDocument()
    await user.click(within(barra).getByRole('button', { name: /No volver a preguntarme por este comercio/ }))
    await waitFor(() =>
      expect(api.accionPorCategorizar).toHaveBeenCalledWith({ accion: 'no_preguntar', huellas: ['kopi zebra'], movimiento_ids: [] })
    )
    await user.click(await screen.findByRole('button', { name: /Deshacer/ }))
    await waitFor(() =>
      expect(api.deshacerPorCategorizar).toHaveBeenCalledWith(
        expect.objectContaining({ huellas: ['kopi zebra'], tipo_silencio: 'no_preguntar' })
      )
    )
  })

  it('«Dejar como están» y «Ocultar de esta lista» llaman a la acción correcta', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: 'Seleccionar los visibles' }))
    await user.click(screen.getByRole('button', { name: /Dejar como están/ }))
    await waitFor(() => expect(api.accionPorCategorizar.mock.calls[0][0].accion).toBe('dejar'))
    expect(api.accionPorCategorizar.mock.calls[0][0].huellas).toHaveLength(3)
    await user.click(await screen.findByRole('button', { name: 'Seleccionar los visibles' }))
    await user.click(screen.getByRole('button', { name: /Ocultar de esta lista/ }))
    await waitFor(() => expect(api.accionPorCategorizar.mock.calls[1][0].accion).toBe('ocultar'))
  })

  it('«Ponerles categoría…» a un comercio: la regla es opcional y viene activada porque se repite 3 veces', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('checkbox', { name: /Seleccionar kopi zebra/ }))
    await user.click(screen.getByRole('button', { name: /Ponerles categoría/ }))
    const recordar = await screen.findByRole('checkbox', { name: /Recordar para este comercio/ })
    await waitFor(() => expect(recordar).toBeChecked()) // 2 más + este = 3
    expect(screen.getByTestId('vista-previa-regla')).toHaveTextContent('Afectará 2 movimientos pasados y los futuros.')
    await user.click(recordar) // la persona la apaga
    await user.click(screen.getByRole('button', { name: /Comida/ }))
    await waitFor(() =>
      expect(api.accionPorCategorizar).toHaveBeenCalledWith(
        expect.objectContaining({ accion: 'categoria', categoria: 'Comida', recordar: false })
      )
    )
  })

  it('en una compra única la regla viene apagada', async () => {
    api.similaresConteo.mockResolvedValue({ conteo: 0 })
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('checkbox', { name: /Seleccionar tienda rara/ }))
    await user.click(screen.getByRole('button', { name: /Ponerles categoría/ }))
    const recordar = await screen.findByRole('checkbox', { name: /Recordar para este comercio/ })
    await waitFor(() => expect(api.similaresConteo).toHaveBeenCalled())
    expect(recordar).not.toBeChecked()
  })

  it('estado vacío amable cuando no hay nada', async () => {
    api.porCategorizar.mockResolvedValue({ ...RESUMEN, conteo: { total: 0, otros: 0, baja: 0, marcadas: 0, silenciados: 0 }, total_grupos: 0, relevantes: 0, grupos: [] })
    montar()
    expect(await screen.findByText('Todo en orden')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /1 minuto/ })).toBeNull()
  })

  it('si solo quedan compras sueltas, celebra con criterio y dice que pueden quedarse', async () => {
    api.porCategorizar.mockResolvedValue({ ...RESUMEN, relevantes: 0, total_grupos: 1, grupos: [{ ...GRUPOS[2] }], conteo: { ...RESUMEN.conteo, total: 1 } })
    montar()
    expect(await screen.findByText('Lo importante ya está categorizado')).toBeInTheDocument()
    expect(screen.getByText(/Pueden quedarse como están/)).toBeInTheDocument()
  })

  it('«Ver todos» pide la lista completa', async () => {
    api.porCategorizar.mockResolvedValueOnce({ ...RESUMEN, hay_mas: true, total_grupos: 14 })
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /Ver todos \(14\)/ }))
    await waitFor(() => expect(api.porCategorizar).toHaveBeenLastCalledWith(10, true))
  })

  it('lista los comercios silenciados y permite volver a preguntar', async () => {
    api.silenciosPorCategorizar.mockResolvedValue({ silencios: [{ huella: 'netflix', tipo: 'ocultar' }] })
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /Comercios que no quieres ver \(1\)/ }))
    await user.click(screen.getByRole('button', { name: /Volver a preguntarme por netflix/ }))
    await waitFor(() => expect(api.quitarSilencios).toHaveBeenCalledWith(['netflix']))
  })
})
