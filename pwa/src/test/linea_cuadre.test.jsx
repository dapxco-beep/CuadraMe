// La línea de cuadre por cuenta: dice el estado, el motivo y la acción, y lleva al cuadre mes a mes.
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LineaCuadre from '../components/LineaCuadre'

const ver = (item) => render(<MemoryRouter><LineaCuadre item={item} /></MemoryRouter>)

describe('LineaCuadre', () => {
  it('cuadra: marca ✓ y el mes', () => {
    ver({ estado: 'cuadra', texto: 'Cuadra a junio', motivo: 'Tus movimientos coinciden con el saldo de tu banco.', accion: null, ruta: '/sincronizacion#cuadre' })
    const l = screen.getByTestId('linea-cuadre')
    expect(l.textContent).toContain('✓ Cuadra a junio')
    expect(l.getAttribute('href')).toBe('/sincronizacion')
  })

  it('no cuadra: marca ✕, diferencia y siguiente paso', () => {
    ver({ estado: 'no_cuadra', texto: 'No cuadra en junio (dif. $800.000)', motivo: 'Junio no cuadra.', accion: 'Importa la línea del extracto que falta.', ruta: '/sincronizacion#cuadre' })
    const l = screen.getByTestId('linea-cuadre')
    expect(l.textContent).toContain('✕ No cuadra en junio (dif. $800.000)')
    expect(l.textContent).toContain('Importa la línea del extracto que falta.')
  })

  it('sin saldo: dice que es del extracto y qué hacer', () => {
    ver({ estado: 'sin_saldo', texto: 'Sin saldo del extracto para cuadrar', motivo: 'El extracto de septiembre no trae el saldo.', accion: 'Escribe el saldo que dice tu extracto.' })
    expect(screen.getByTestId('linea-cuadre').textContent).toContain('Escribe el saldo que dice tu extracto.')
  })

  it('sin dato no pinta nada', () => {
    const { container } = ver(null)
    expect(container.textContent).toBe('')
  })
})
