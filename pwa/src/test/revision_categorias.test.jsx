// Revisión de un extracto: cada línea con su categoría (con emoji), cómo quedó categorizada,
// resumen arriba y acción en bloque con «recordar esta regla».
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  obtenerReviewExtracto: vi.fn(),
  importarFaltantes: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Bancolombia', icono: 'B' }], recargar: vi.fn() }),
}))
const EMOJIS = { Comida: '\u{1F354}', Transporte: '\u{1F68C}', Hogar: '\u{1F3E0}', Otros: '\u{1F4B3}' }
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({
    nombres: ['Comida', 'Transporte', 'Hogar', 'Otros'],
    iconoDe: (n) => EMOJIS[n] || '\u{1F4B3}',
  }),
}))

import { estadoCategoria, resumirCategorias, textoResumenCategorias } from '../lib/estadoCategoria'
import { normalizarPdf } from '../lib/subidaMultiple'
import SubidaMultiple from '../components/SubidaMultiple'

const linea = (fp, descripcion, categoria, extra = {}) => ({
  fecha: '2026-09-10', descripcion, monto: 10000, tipo: 'expense', fingerprint: fp, estado: 'faltante',
  categoria_sugerida: categoria, ...extra,
})

const REVIEW = {
  historial_id: 'h1', cuenta_id: 'c1', banco_detectado: 'Bancolombia', total_movimientos: 5,
  review: [
    linea('f1', 'COMPRA RAPPI RESTAURANTE', 'Comida', { razon_categoria: 'regla tuya', confianza_categoria: 1 }),
    linea('f2', 'TRANSMILENIO RECARGA', 'Transporte', { razon_categoria: 'comercio conocido', confianza_categoria: 0.9 }),
    linea('f3', 'PAGO TIENDA DON PEPE', 'Hogar', { razon_categoria: 'parecido a otros', confianza_categoria: 0.4 }),
    linea('f4', 'ABONO MISTERIOSO XYZ', 'Otros'),
    linea('f5', 'COMPRA ANTIGUA', 'Comida', { estado: 'anterior' }),
  ],
}

const montar = () =>
  render(
    <MemoryRouter>
      <SubidaMultiple revisionInicial={{ historialId: 'h1' }} onCancelar={vi.fn()} />
    </MemoryRouter>
  )

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  api.obtenerReviewExtracto.mockResolvedValue(REVIEW)
  api.importarFaltantes.mockResolvedValue({ ok: true, importados: 4 })
})

describe('estado de categorización (reglas puras)', () => {
  it('distingue automática, por revisar, sin categoría y elegida por ti', () => {
    expect(estadoCategoria({ categoria: 'Comida', razon: 'regla', confianza: 1 })).toBe('auto')
    expect(estadoCategoria({ categoria: 'Hogar', razon: 'parecido', confianza: 0.4 })).toBe('revisar')
    expect(estadoCategoria({ categoria: 'Otros' })).toBe('sin_categoria')
    expect(estadoCategoria({ categoria: 'Otros' }, 'Hogar')).toBe('confirmada')
    expect(estadoCategoria({ categoria: 'Comida', razon: 'x', confianza: 1 }, 'Otros')).toBe('sin_categoria')
    // sin confianza numérica (archivos Excel/CSV): manda la razón
    expect(estadoCategoria({ categoria: 'Comida', razon: 'palabra clave' })).toBe('auto')
    expect(estadoCategoria({ categoria: 'Comida' })).toBe('revisar')
  })

  it('resume en «37 categorizados, 5 por revisar»', () => {
    const r = resumirCategorias([...Array(37).fill('auto'), ...Array(5).fill('revisar')])
    expect(textoResumenCategorias(r)).toBe('37 categorizados, 5 por revisar')
    expect(textoResumenCategorias(resumirCategorias(['auto', 'sin_categoria']))).toBe('1 categorizado, 0 por revisar, 1 sin categoría')
  })

  it('normalizarPdf trae la confianza y deja las líneas anteriores aparte', () => {
    const n = normalizarPdf(REVIEW)
    expect(n.items.find((i) => i.k === 'f3')).toMatchObject({ confianza: 0.4, estado: 'nuevo' })
    expect(n.items.find((i) => i.k === 'f5').estado).toBe('anterior')
    expect(n.anteriores).toBe(1)
  })
})

describe('revisión del extracto', () => {
  it('cada línea muestra su categoría con emoji y su estado, y arriba el resumen', async () => {
    montar()
    const resumen = await screen.findByTestId('resumen-categorias')
    expect(within(resumen).getByText('2 categorizados, 1 por revisar, 1 sin categoría')).toBeInTheDocument()

    const chips = screen.getAllByTestId('chip-categoria')
    expect(chips).toHaveLength(4) // la línea «anterior» no se ofrece
    expect(chips[0]).toHaveTextContent(`${EMOJIS.Comida}`)
    expect(chips[0]).toHaveTextContent('Comida')
    expect(chips[0]).toHaveAttribute('data-estado', 'auto')
    expect(chips[0]).toHaveTextContent('Categorizado automáticamente')
    expect(chips[2]).toHaveAttribute('data-estado', 'revisar')
    expect(chips[2]).toHaveTextContent('Necesita tu revisión')
    expect(chips[3]).toHaveAttribute('data-estado', 'sin_categoria')
    expect(chips[3]).toHaveTextContent('Sin categoría')
    expect(screen.getByTestId('aviso-anteriores')).toHaveTextContent('1 línea es anterior a tu fecha de inicio')
  })

  it('las opciones del selector llevan el emoji de cada categoría', async () => {
    montar()
    const sel = await screen.findByLabelText('Categoría de PAGO TIENDA DON PEPE')
    const opcion = within(sel).getByRole('option', { name: `${EMOJIS.Transporte} Transporte` })
    expect(opcion).toBeInTheDocument()
  })

  it('«Marcar las por revisar» + acción en bloque aplica la categoría y recuerda la regla', async () => {
    montar()
    await screen.findByTestId('resumen-categorias')
    await userEvent.click(screen.getByRole('button', { name: /Marcar las 1 por revisar/ }))
    const bloque = screen.getByTestId('categoria-en-bloque')
    expect(within(bloque).getByText('Poner una categoría a las 1 marcada')).toBeInTheDocument()
    await userEvent.selectOptions(within(bloque).getByLabelText('Categoría para las marcadas'), 'Comida')
    expect(within(bloque).getByRole('checkbox')).toBeChecked() // «Recordar esta regla» viene marcada
    await userEvent.click(within(bloque).getByRole('button', { name: /Aplicar a las 1/ }))

    // la línea quedó «elegida por ti» y el resumen se actualiza
    expect(await screen.findByText('3 categorizados, 0 por revisar, 1 sin categoría')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^Importar \(1\)$/ }))
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalled())
    const [historial, fps, categorias, aprender] = api.importarFaltantes.mock.calls[0]
    expect(historial).toBe('h1')
    expect(fps).toEqual(['f3'])
    expect(categorias).toEqual({ f3: 'Comida' })
    expect(aprender.recordar).toEqual(['f3']) // se guarda la regla del comercio
  })

  it('sin «recordar», la categoría solo vale para esta revisión', async () => {
    montar()
    await screen.findByTestId('resumen-categorias')
    await userEvent.click(screen.getByRole('button', { name: /Marcar las 1 sin categoría/ }))
    const bloque = screen.getByTestId('categoria-en-bloque')
    await userEvent.selectOptions(within(bloque).getByLabelText('Categoría para las marcadas'), 'Hogar')
    await userEvent.click(within(bloque).getByRole('checkbox'))
    await userEvent.click(within(bloque).getByRole('button', { name: /Aplicar a las 1/ }))
    await userEvent.click(await screen.findByRole('button', { name: /^Importar \(1\)$/ }))
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalled())
    const [, fps, categorias, aprender] = api.importarFaltantes.mock.calls[0]
    expect(fps).toEqual(['f4'])
    expect(categorias).toEqual({ f4: 'Hogar' })
    expect(aprender.recordar).toEqual([])
  })
})
