import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import TablaMovimientos from '../components/TablaMovimientos'

const items = [
  { id: 'a', descripcion: 'Nómina', categoria: 'Ingresos', tipo: 'income', monto: 5000000, fecha: '2026-10-12T08:00:00', cuenta_id: 'c1', fuente: 'manual', notas: '' },
  { id: 'b', descripcion: 'Jumbo', categoria: 'Comida', tipo: 'expense', monto: 260000, fecha: '2026-10-24T11:00:00', cuenta_id: 'c1', fuente: 'manual', notas: '' },
]
const base = {
  items, iconoDe: () => '💳', monedaDe: { c1: 'COP' }, nombreCuenta: () => 'Cuenta', panelId: null,
  onToggle() {}, onToggleTodos() {}, onAbrir() {}, onChip() {},
}
const pintar = (extra) => render(<MemoryRouter><TablaMovimientos {...base} {...extra} /></MemoryRouter>)

describe('Tabla de movimientos: totales', () => {
  it('muestra cuánto entró, cuánto salió y el neto junto al conteo', () => {
    pintar({ seleccionados: new Set(), totales: { ingresos: 5000000, gastos: 260000, neto: 4740000 } })
    const t = screen.getByTestId('tabla-totales')
    expect(t).toHaveTextContent('2 movimientos')
    expect(t).toHaveTextContent('Entró')
    expect(t).toHaveTextContent('Salió')
    expect(t).toHaveTextContent('+')
    expect(screen.queryByTestId('tabla-total-seleccion')).toBeNull()
  })

  it('con filas marcadas suma lo seleccionado y pinta en rojo un neto negativo', () => {
    pintar({ seleccionados: new Set(['b']), totales: { ingresos: 0, gastos: 260000, neto: -260000 }, netoSeleccion: -260000 })
    expect(screen.getByTestId('tabla-total-seleccion')).toHaveTextContent('1 seleccionado')
    expect(screen.getByTestId('tabla-total-seleccion')).toHaveTextContent('-')
  })

  it('sin totales (otra pantalla que use la tabla) solo cuenta los movimientos', () => {
    pintar({ seleccionados: new Set() })
    expect(screen.getByTestId('tabla-totales')).toHaveTextContent('2 movimientos')
    expect(screen.getByTestId('tabla-totales')).not.toHaveTextContent('Entró')
  })
})
