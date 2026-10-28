import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({ useCuentas: () => ({ cuentas: [], cargando: false, error: '', recargar: vi.fn() }) }))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ nombres: [], iconoDe: () => '' }) }))
vi.mock('../components/CierreExtractos', () => ({ default: ({ datos }) => <p>Detalle de extractos ({datos.bancos.length} bancos)</p> }))

import { DialogosProvider } from '../lib/DialogosContext'
import CierreMes from '../screens/CierreMes'

function Sonda() {
  return <p data-testid="ruta">{useLocation().pathname}</p>
}
const montar = () =>
  render(
    <DialogosProvider>
      <MemoryRouter initialEntries={['/cierre-mes']}>
        <Routes>
          <Route path="/cierre-mes" element={<CierreMes />} />
          <Route path="*" element={<p>otra pantalla</p>} />
        </Routes>
        <Sonda />
      </MemoryRouter>
    </DialogosProvider>
  )

const EXT = (estado) => ({ hay_datos: true, etiqueta: 'Septiembre', bancos: [{ banco: 'Nu', cuentas: [{ cuenta_id: 'c1', estado, diferencia: 40000 }] }], meses: [] })
const INFORME = {
  titulo: 'Septiembre', resumen_corto: 'Un buen mes', ingresos: 4000000, gastos: 3000000, ahorro: 1000000, tasa_ahorro: 25,
  intereses_pagados: 0, patrimonio: null, categoria_que_mas_subio: null, acciones: ['Revisa Comida'],
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    cierrePreferencias: vi.fn().mockResolvedValue({ correo: false }),
    guardarCierrePreferencias: vi.fn().mockResolvedValue({ ok: true }),
    cierresMes: vi.fn().mockResolvedValue([]),
    cierreMes: vi.fn().mockResolvedValue(null),
    generarCierreMes: vi.fn().mockResolvedValue(INFORME),
    cierreExtractos: vi.fn().mockResolvedValue(EXT('cuadra')),
    sincronizacionPorCategorizar: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    alertasProactivas: vi.fn().mockResolvedValue({ comisiones: [], cobros_duplicados: [] }),
  })
})

describe('asistente de cierre de mes', () => {
  it('empieza por «¿Cuadran tus cuentas?» y dice cómo van las cuentas', async () => {
    montar()
    expect(await screen.findByRole('heading', { name: /¿Cuadran tus cuentas\?/ })).toBeTruthy()
    expect(await screen.findByText('Todas tus cuentas cuadran con el banco.')).toBeTruthy()
    expect(screen.getByText(/Paso 1 de 4/)).toBeTruthy()
    expect(screen.getByText('Detalle de extractos (1 bancos)')).toBeTruthy()
  })

  it('con todo en orden avisa «ya puedes cerrar» y genera el cierre', async () => {
    const user = userEvent.setup()
    montar()
    await screen.findByText('Todas tus cuentas cuadran con el banco.')
    await user.click(screen.getByRole('button', { name: /Paso 4/ }))
    expect(await screen.findByText('Todo en orden. Ya puedes cerrar el mes.')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Generar cierre' }))
    await waitFor(() => expect(api.generarCierreMes).toHaveBeenCalled())
    expect(await screen.findByText('Un buen mes')).toBeTruthy()
  })

  it('una cuenta que no cuadra pide atención y manda a traer extractos', async () => {
    api.cierreExtractos.mockResolvedValue(EXT('no_cuadra'))
    const user = userEvent.setup()
    montar()
    expect(await screen.findByText('1 cuenta no cuadra con tu banco.')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Traer los extractos que faltan' }))
    await waitFor(() => expect(screen.getByTestId('ruta').textContent).toBe('/sincronizacion'))
  })

  it('las categorías pendientes se cuentan y llevan a ponerlas', async () => {
    api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 12 })
    const user = userEvent.setup()
    montar()
    await screen.findByText('Todas tus cuentas cuadran con el banco.')
    await user.click(screen.getByRole('button', { name: /Siguiente: Categorías/ }))
    expect(await screen.findByText('12 comercios sin categoría.')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Ponerles categoría' }))
    await waitFor(() => expect(screen.getByTestId('ruta').textContent).toBe('/categorizar'))
  })

  it('lo raro se lista en palabras simples', async () => {
    api.alertasProactivas.mockResolvedValue({
      comisiones: [{ descripcion: 'Cuota de manejo', total_mes: 20000, veces: 1 }],
      cobros_duplicados: [{ movimiento_id_1: 'm1', descripcion: 'Netflix', monto: 30000 }],
    })
    const user = userEvent.setup()
    montar()
    await screen.findByText('Todas tus cuentas cuadran con el banco.')
    await user.click(screen.getByRole('button', { name: /Paso 3/ }))
    expect(await screen.findByText('2 cosas para mirar.')).toBeTruthy()
    expect(screen.getByText('Cuota de manejo')).toBeTruthy()
    expect(screen.getByText(/Posible cobro repetido: Netflix/)).toBeTruthy()
  })

  it('antes de cerrar lista lo que falta y deja saltar a cada paso o cerrar de todos modos', async () => {
    api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 3 })
    const user = userEvent.setup()
    montar()
    await screen.findByText('Todas tus cuentas cuadran con el banco.')
    await user.click(screen.getByRole('button', { name: /Paso 4/ }))
    const caja = await screen.findByTestId('faltan-antes-de-cerrar')
    await user.click(within(caja).getByRole('button', { name: /3 comercios sin categoría/ }))
    expect(await screen.findByRole('heading', { name: /¿Todo tiene categoría\?/ })).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /Paso 4/ }))
    await user.click(await screen.findByRole('button', { name: 'Generar cierre de todos modos' }))
    await waitFor(() => expect(api.generarCierreMes).toHaveBeenCalled())
  })

  it('si el cierre ya existe se abre directo en el resumen', async () => {
    api.cierresMes.mockResolvedValue([{ mes: '2026-09' }])
    api.cierreMes.mockResolvedValue(INFORME)
    montar()
    expect(await screen.findByText('Un buen mes')).toBeTruthy()
    expect(screen.getByText(/Paso 4 de 4/)).toBeTruthy()
  })

  it('no se rompe si el servidor no responde los pasos opcionales', async () => {
    api.alertasProactivas.mockRejectedValue(new Error('x'))
    api.sincronizacionPorCategorizar.mockRejectedValue(new Error('x'))
    api.cierreExtractos.mockRejectedValue(new Error('x'))
    montar()
    expect(await screen.findByText('No pude comparar con tus extractos ahora. Puedes seguir.')).toBeTruthy()
  })
})
