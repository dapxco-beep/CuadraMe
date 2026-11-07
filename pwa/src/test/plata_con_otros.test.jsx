import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import PlataConOtros, { OPCIONES } from '../screens/PlataConOtros'
import { ITEMS_MAS } from '../lib/navegacion'

const montar = () => render(<MemoryRouter><PlataConOtros /></MemoryRouter>)

describe('Plata con otros: una sola puerta', () => {
  it('muestra Dividir, Parche y Vaca, cada uno con su ejemplo y su destino', () => {
    montar()
    expect(screen.getByRole('heading', { name: 'Plata con otros', level: 1 })).toBeInTheDocument()
    expect(OPCIONES.map((o) => o.titulo)).toEqual(['Dividir un gasto', 'Parche', 'Vaca'])
    expect(screen.getByRole('link', { name: /Dividir un gasto/ })).toHaveAttribute('href', '/amigos')
    expect(screen.getByRole('link', { name: /Parche/ })).toHaveAttribute('href', '/hogares')
    expect(screen.getByRole('link', { name: /Vaca/ })).toHaveAttribute('href', '/colectas')
    expect(screen.getByText(/Tu amigo no necesita CuadraMe/)).toBeInTheDocument()
  })

  it('«dar acceso a mis cuentas» queda aparte, como otra cosa', () => {
    montar()
    expect(screen.getByRole('link', { name: 'dar acceso a mis cuentas' })).toHaveAttribute('href', '/compartir')
  })

  it('el menú tiene UNA entrada y el buscador sigue encontrando vaca, parche y dividir', () => {
    const e = ITEMS_MAS.filter((i) => i.to === '/otros')
    expect(e).toHaveLength(1)
    for (const palabra of ['vaca', 'parche', 'dividir', 'me deben']) expect(e[0].palabras).toContain(palabra)
    expect(ITEMS_MAS.some((i) => ['/amigos', '/hogares', '/colectas', '/compartir'].includes(i.to))).toBe(false)
  })
})
