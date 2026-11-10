import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import FilaDeslizable from '../components/FilaDeslizable'

// jsdom no trae PointerEvent con coordenadas: se arma el evento a mano
function puntero(el, tipo, x, y, pointerType = 'touch') {
  const ev = new Event(tipo, { bubbles: true, cancelable: true })
  Object.assign(ev, { clientX: x, clientY: y, pointerType, pointerId: 1 })
  act(() => {
    el.dispatchEvent(ev)
  })
}

function montar(extra = {}) {
  const onCat = vi.fn()
  const onBorrar = vi.fn()
  render(
    <div>
      <FilaDeslizable
        acciones={[
          { id: 'categoria', texto: 'Categoría', onClick: onCat },
          { id: 'borrar', texto: 'Borrar', tono: 'peligro', confirmar: true, onClick: onBorrar },
        ]}
        {...extra}
      >
        <p>Fila de prueba</p>
      </FilaDeslizable>
      <button>fuera</button>
    </div>
  )
  return { onCat, onBorrar, contenido: screen.queryByTestId('contenido-fila') }
}

const abrir = (c) => {
  puntero(c, 'pointerdown', 200, 50)
  puntero(c, 'pointermove', 100, 52)
  puntero(c, 'pointerup', 100, 52)
}

describe('FilaDeslizable', () => {
  it('queda cerrada, con touch-action pan-y y acciones fuera del árbol de accesibilidad', () => {
    const { contenido } = montar()
    expect(contenido.style.touchAction).toBe('pan-y')
    expect(screen.getByTestId('acciones-fila')).toHaveAttribute('aria-hidden', 'true')
    expect(contenido.style.transform).toBe('')
  })

  it('al deslizar a la izquierda muestra 2 acciones de 72 px', () => {
    const { contenido } = montar()
    abrir(contenido)
    expect(contenido.style.transform).toBe('translateX(-144px)')
    expect(screen.getByTestId('acciones-fila')).toHaveAttribute('aria-hidden', 'false')
  })

  it('un gesto vertical no abre la fila (deja el scroll)', () => {
    const { contenido } = montar()
    puntero(contenido, 'pointerdown', 200, 50)
    puntero(contenido, 'pointermove', 190, 120)
    puntero(contenido, 'pointerup', 190, 120)
    expect(contenido.style.transform).toBe('')
  })

  it('el ratón no desliza', () => {
    const { contenido } = montar()
    puntero(contenido, 'pointerdown', 200, 50, 'mouse')
    puntero(contenido, 'pointermove', 100, 50, 'mouse')
    puntero(contenido, 'pointerup', 100, 50, 'mouse')
    expect(contenido.style.transform).toBe('')
  })

  it('se cierra al deslizar de vuelta, al tocar fuera y con Escape', () => {
    const { contenido } = montar()
    abrir(contenido)
    puntero(contenido, 'pointerdown', 100, 50)
    puntero(contenido, 'pointermove', 220, 50)
    puntero(contenido, 'pointerup', 220, 50)
    expect(contenido.style.transform).toBe('')

    abrir(contenido)
    puntero(screen.getByText('fuera'), 'pointerdown', 5, 5)
    expect(contenido.style.transform).toBe('')

    abrir(contenido)
    fireEvent.keyDown(contenido, { key: 'Escape' })
    expect(contenido.style.transform).toBe('')
  })

  it('Categoría actúa de una; Borrar pide un segundo toque', async () => {
    const { contenido, onCat, onBorrar } = montar()
    abrir(contenido)
    await new Promise((r) => setTimeout(r, 80))
    fireEvent.click(screen.getByText('Borrar'))
    expect(onBorrar).not.toHaveBeenCalled()
    expect(screen.getByText('¿Seguro?')).toBeInTheDocument()
    fireEvent.click(screen.getByText('¿Seguro?'))
    expect(onBorrar).toHaveBeenCalledTimes(1)
    expect(contenido.style.transform).toBe('')

    abrir(contenido)
    await new Promise((r) => setTimeout(r, 80))
    fireEvent.click(screen.getByText('Categoría'))
    expect(onCat).toHaveBeenCalledTimes(1)
  })

  it('sin acciones o desactivada no envuelve nada', () => {
    montar({ desactivada: true })
    expect(screen.queryByTestId('acciones-fila')).toBeNull()
    expect(screen.getByText('Fila de prueba')).toBeInTheDocument()
  })
})
