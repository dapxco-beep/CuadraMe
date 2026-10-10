// Subir un archivo de un periodo+cuenta que ya estaba conciliado: se avisa, no se bloquea.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  procesarExtracto: vi.fn(),
  importarVistaPrevia: vi.fn(),
  importarConfirmar: vi.fn(),
  importarFaltantes: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Nu', icono: '💜' }], recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Otros'], iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { normalizarPdf, normalizarTabular } from '../lib/subidaMultiple'
import AvisoYaConciliado from '../components/AvisoYaConciliado'
import SubidaMultiple from '../components/SubidaMultiple'

const montar = (ui) =>
  render(
    <DialogosProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

describe('aviso de periodo ya conciliado', () => {
  it('dice cuenta, mes y movimientos cruzados, y deja seguir', () => {
    montar(<AvisoYaConciliado info={{ mes: '2026-09', cruzados: 12 }} cuenta="Nu" />)
    expect(screen.getByText('Este periodo de Nu ya lo revisamos con tu extracto: ¿quieres revisarlo otra vez?')).toBeInTheDocument()
    expect(screen.getByText(/Septiembre 2026 · 12 movimientos coinciden con el banco/)).toBeInTheDocument()
    expect(screen.getByText(/no se duplica/)).toBeInTheDocument()
  })

  it('no muestra nada si el periodo no estaba conciliado', () => {
    const { container } = montar(<AvisoYaConciliado info={null} cuenta="Nu" />)
    expect(container.querySelector('[data-testid="aviso-ya-conciliado"]')).toBeNull()
  })

  it('los normalizadores conservan el aviso que manda el servidor', () => {
    const info = { mes: '2026-09', cruzados: 3 }
    expect(normalizarPdf({ review: [], ya_conciliado: info }).yaConciliado).toEqual(info)
    expect(normalizarTabular({ propuesta: [], ya_conciliado: info }).yaConciliado).toEqual(info)
    expect(normalizarTabular({ propuesta: [] }).yaConciliado).toBeNull()
  })

  it('en la subida múltiple avisa en el archivo afectado sin impedir revisarlo', async () => {
    api.procesarExtracto.mockResolvedValue({
      ok: true, historial_id: 'h1', banco_detectado: 'nu', total_movimientos: 1, periodo_desde: '2026-09-01', periodo_hasta: '2026-09-30',
      ya_conciliado: { mes: '2026-09', cruzados: 5 },
      review: [{ fingerprint: 'fp1', fecha: '2026-09-03', descripcion: 'CAFE', monto: 9000, tipo: 'expense', estado: 'faltante', categoria_sugerida: 'Otros' }],
    })
    const pdf = new File(['%PDF-1.4'], 'sep.pdf', { type: 'application/pdf' })
    montar(<SubidaMultiple archivosIniciales={[pdf]} cuentaInicial="c1" onCancelar={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Procesar/ }))
    expect(await screen.findByText('Este periodo de Nu ya lo revisamos con tu extracto: ¿quieres revisarlo otra vez?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Revisar/ })).toBeEnabled()
  })
})
