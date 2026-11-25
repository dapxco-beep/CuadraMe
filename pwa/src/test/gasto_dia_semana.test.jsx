import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import GastoPorDiaSemana, { hallazgoDiaSemana, promediosPorDiaSemana } from '../components/GastoPorDiaSemana'

const fmt = (n) => `$${n}`

// 4 semanas desde el lunes 2026-10-05: los sábados se gastan 100.000 y el resto de días 10.000
function mes() {
  const dias = []
  for (let i = 0; i < 28; i++) {
    const f = new Date(2026, 9, 5 + i)
    const iso = `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}-${String(f.getDate()).padStart(2, '0')}`
    dias.push({ dia: iso, gasto: f.getDay() === 6 ? 100_000 : 10_000 })
  }
  return dias
}

describe('Gasto por día de la semana', () => {
  it('promedia por día de la semana, de lunes a domingo', () => {
    const p = promediosPorDiaSemana(mes())
    expect(p).toHaveLength(7)
    expect(p[0]).toMatchObject({ promedio: 10_000, dias: 4 }) // lunes
    expect(p[5]).toMatchObject({ promedio: 100_000, dias: 4 }) // sábado
  })

  it('encuentra el día más caro y cuánto pesa frente al resto', () => {
    const h = hallazgoDiaSemana(promediosPorDiaSemana(mes()))
    expect(h.nombre).toBe('sábados')
    expect(h.vsResto).toBe(900)
  })

  it('con pocos datos no dice nada', () => {
    expect(hallazgoDiaSemana(promediosPorDiaSemana(mes().slice(0, 3)))).toBeNull()
    const { container } = render(<GastoPorDiaSemana dias={mes().slice(0, 10)} fmt={fmt} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('muestra la frase y la gráfica con dos semanas o más', () => {
    render(<GastoPorDiaSemana dias={mes()} fmt={fmt} />)
    expect(screen.getByText('¿Qué día gastas más?')).toBeInTheDocument()
    expect(screen.getByText('sábados')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /sábados \$100000/ })).toBeInTheDocument()
  })
})
