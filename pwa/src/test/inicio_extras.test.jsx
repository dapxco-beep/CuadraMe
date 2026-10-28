import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AccionesRapidas, AvisoNegativo, EsteMes } from '../components/InicioExtras'
import { cuentasEnNegativo } from '../lib/inicioSimple'

const fmt = (n) => `$${n}`
const cuentas = [
  { id: 'a', nombre: 'Efectivo', tipo: 'efectivo', saldo: 300000, moneda: 'COP' },
  { id: 'b', nombre: 'Nequi', tipo: 'ahorro', saldo: -980119, moneda: 'COP' },
  { id: 'c', nombre: 'Nu Crédito', tipo: 'credito', saldo: -50000, moneda: 'COP' },
  { id: 'd', nombre: 'Nu Colombia', tipo: 'ahorro', saldo: -1924168, moneda: 'COP' },
]

describe('Inicio: bloques prácticos', () => {
  it('cuentasEnNegativo ignora tarjetas y saldos positivos, la más negativa primero', () => {
    expect(cuentasEnNegativo(cuentas).map((c) => c.id)).toEqual(['d', 'b'])
  })

  it('el aviso explica el negativo con las cuentas que lo causan; con saldo positivo no sale', () => {
    const { rerender } = render(<MemoryRouter><AvisoNegativo saldo={-2604287} cuentas={cuentas} fmt={fmt} /></MemoryRouter>)
    expect(screen.getByTestId('aviso-negativo')).toHaveTextContent('Nequi')
    expect(screen.getByTestId('aviso-negativo')).toHaveTextContent('Nu Colombia')
    expect(screen.getByTestId('aviso-negativo')).not.toHaveTextContent('Nu Crédito')
    rerender(<MemoryRouter><AvisoNegativo saldo={100} cuentas={cuentas} fmt={fmt} /></MemoryRouter>)
    expect(screen.queryByTestId('aviso-negativo')).toBeNull()
  })

  it('acciones rápidas por defecto: gasto, ingreso, pasar plata y traer (solo cuatro)', () => {
    localStorage.clear()
    render(<MemoryRouter><AccionesRapidas /></MemoryRouter>)
    const hrefs = within(screen.getByTestId('acciones-rapidas')).getAllByRole('link').map((a) => a.getAttribute('href'))
    expect(hrefs).toEqual([
      '/agregar?foco=monto', '/agregar?tipo=income&foco=monto', '/agregar?tipo=transfer', '/sincronizacion',
    ])
  })

  it('quien ya eligió sus accesos conserva los suyos (solo cambia el valor por defecto)', () => {
    localStorage.clear()
    localStorage.setItem('cuadrame:accesos-inicio:anon', JSON.stringify(['gasto', 'ingreso', 'pasar', 'traer', 'dividir', 'metas', 'deudas', 'fijos']))
    render(<MemoryRouter><AccionesRapidas /></MemoryRouter>)
    const hrefs = within(screen.getByTestId('acciones-rapidas')).getAllByRole('link').map((a) => a.getAttribute('href'))
    expect(hrefs).toHaveLength(8)
    expect(hrefs.slice(4)).toEqual(['/amigos', '/metas', '/deudas', '/recurrentes'])
  })

  it('Personalizar: la persona elige sus accesos y se recuerdan', async () => {
    localStorage.clear()
    render(<MemoryRouter><AccionesRapidas /></MemoryRouter>)
    fireEvent.click(screen.getByTestId('personalizar-accesos'))
    const hoja = within(await screen.findByTestId('hoja-accesos'))
    fireEvent.click(hoja.getByRole('button', { name: /Ingreso/ })) // quita Ingreso
    fireEvent.click(hoja.getByRole('button', { name: /Presupuesto/ })) // pone Presupuesto al final
    fireEvent.click(hoja.getByRole('button', { name: 'Listo' }))
    const hrefs = within(screen.getByTestId('acciones-rapidas')).getAllByRole('link').map((a) => a.getAttribute('href'))
    expect(hrefs).not.toContain('/agregar?tipo=income&foco=monto')
    expect(hrefs[hrefs.length - 1]).toBe('/presupuesto')
    expect(hrefs).toContain('/sincronizacion')
  })

  it('Este mes muestra entró, salió y neto, y no sale sin movimientos', () => {
    const reporte = { ingresos: 5000000, gastos: 3000000, top_categorias: [{ categoria: 'Comida', monto: 900000 }] }
    const { rerender } = render(<MemoryRouter><EsteMes reporte={reporte} fmt={fmt} iconoDe={() => '🍔'} /></MemoryRouter>)
    expect(screen.getByTestId('este-mes')).toHaveTextContent('+$2000000')
    expect(screen.getByTestId('este-mes')).toHaveTextContent('Comida')
    rerender(<MemoryRouter><EsteMes reporte={{ ingresos: 0, gastos: 0, top_categorias: [] }} fmt={fmt} iconoDe={() => ''} /></MemoryRouter>)
    expect(screen.queryByTestId('este-mes')).toBeNull()
  })
})
