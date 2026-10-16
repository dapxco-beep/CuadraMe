// La conciliación se puede retomar: crear una categoría NO saca de la revisión (hoja encima, queda elegida)
// y, si la revisión se cierra a medias, al volver están las mismas marcas y categorías (borrador).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  obtenerReviewExtracto: vi.fn(),
  importarFaltantes: vi.fn(),
  crearCategoria: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Nu Colombia', icono: 'N' }], recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Hogar', 'Otros'], iconoDe: () => '\u{1F4B3}', recargar: vi.fn() }),
}))

import SubidaMultiple from '../components/SubidaMultiple'
import { leerBorrador } from '../lib/retomar'

const linea = (fp, descripcion, categoria) => ({
  fecha: '2026-09-10', descripcion, monto: 10000, tipo: 'expense', fingerprint: fp, estado: 'faltante', categoria_sugerida: categoria,
})
const REVIEW = {
  historial_id: 'h1', cuenta_id: 'c1', banco_detectado: 'Nu', total_movimientos: 2,
  review: [linea('f1', 'COMPRA RAPPI RESTAURANTE', 'Comida'), linea('f2', 'PAGO TIENDA DON PEPE', 'Hogar')],
}
const montar = () => render(<MemoryRouter><SubidaMultiple revisionInicial={{ historialId: 'h1' }} onCancelar={vi.fn()} /></MemoryRouter>)

beforeEach(() => {
  sessionStorage.clear()
  Object.values(api).forEach((f) => f.mockReset())
  api.obtenerReviewExtracto.mockResolvedValue(REVIEW)
  api.crearCategoria.mockResolvedValue({ ok: true })
})

describe('crear categoría sin salir de la revisión', () => {
  it('abre una hoja, crea la categoría, la deja elegida y la revisión sigue ahí', async () => {
    const user = userEvent.setup()
    montar()
    const sel = await screen.findByLabelText('Categoría de COMPRA RAPPI RESTAURANTE')
    await user.selectOptions(sel, '__nueva_categoria__')
    await user.type(await screen.findByLabelText('Nombre'), 'Mascotas')
    await user.click(screen.getByRole('button', { name: 'Crear y elegir' }))
    await waitFor(() => expect(api.crearCategoria).toHaveBeenCalledWith(expect.objectContaining({ nombre: 'Mascotas' })))
    await waitFor(() => expect(screen.getByLabelText('Categoría de COMPRA RAPPI RESTAURANTE').value).toBe('Mascotas'))
    expect(screen.getByTestId('revision-multiple')).toBeTruthy()
  })

  it('al volver a abrir la revisión conserva lo que ya habías cambiado', async () => {
    const user = userEvent.setup()
    const primera = montar()
    const sel = await screen.findByLabelText('Categoría de PAGO TIENDA DON PEPE')
    await user.selectOptions(sel, 'Comida')
    await user.click(screen.getByLabelText('Importar COMPRA RAPPI RESTAURANTE')) // la desmarca
    await waitFor(() => expect(leerBorrador('h1')?.categorias.f2).toBe('Comida'))
    primera.unmount()

    montar()
    expect((await screen.findByLabelText('Categoría de PAGO TIENDA DON PEPE')).value).toBe('Comida')
    expect(screen.getByLabelText('Importar COMPRA RAPPI RESTAURANTE').checked).toBe(false)
    expect(screen.getByLabelText('Importar PAGO TIENDA DON PEPE').checked).toBe(true)
  })
})
