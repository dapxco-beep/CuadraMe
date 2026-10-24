import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useJalarParaRefrescar } from '../lib/jalarRefrescar'

function Lista({ onRefrescar }) {
  const jalar = useJalarParaRefrescar(onRefrescar)
  return (
    <div ref={jalar.ref} data-testid="lista">
      {jalar.indicador}
      contenido
    </div>
  )
}

const tocar = (el, tipo, y) => fireEvent(el, new TouchEvent(tipo, { touches: tipo === 'touchend' ? [] : [{ clientY: y }], bubbles: true }))

describe('jalar para refrescar', () => {
  it('jalar con el dedo desde arriba y soltar vuelve a pedir los datos', async () => {
    const refrescar = vi.fn().mockResolvedValue()
    render(<Lista onRefrescar={refrescar} />)
    const el = screen.getByTestId('lista')
    tocar(el, 'touchstart', 100)
    tocar(el, 'touchmove', 260)
    expect(screen.getByTestId('jalar-indicador')).toBeInTheDocument()
    tocar(el, 'touchend', 260)
    await waitFor(() => expect(refrescar).toHaveBeenCalledTimes(1))
  })

  it('un jalón corto no refresca', async () => {
    const refrescar = vi.fn()
    render(<Lista onRefrescar={refrescar} />)
    const el = screen.getByTestId('lista')
    tocar(el, 'touchstart', 100)
    tocar(el, 'touchmove', 110)
    tocar(el, 'touchend', 110)
    await new Promise((r) => setTimeout(r, 50))
    expect(refrescar).not.toHaveBeenCalled()
  })

  it('si la lista ya bajó (scroll), jalar no hace nada', async () => {
    const refrescar = vi.fn()
    render(<Lista onRefrescar={refrescar} />)
    const el = screen.getByTestId('lista')
    Object.defineProperty(el, 'scrollTop', { value: 200, configurable: true })
    tocar(el, 'touchstart', 100)
    tocar(el, 'touchmove', 300)
    tocar(el, 'touchend', 300)
    await new Promise((r) => setTimeout(r, 50))
    expect(refrescar).not.toHaveBeenCalled()
  })
})
