import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import Hoja from '../components/Hoja'

function Demo({ onCerrarExterno = () => {} }) {
  const [abierta, setAbierta] = useState(false)
  return (
    <div>
      <button onClick={() => setAbierta(true)}>Abrir</button>
      {abierta && (
        <Hoja
          titulo="Nueva meta"
          onCerrar={() => {
            onCerrarExterno()
            setAbierta(false)
          }}
        >
          {({ cerrar }) => (
            <div>
              <input aria-label="Nombre" />
              <button onClick={cerrar}>Cerrar hoja</button>
            </div>
          )}
        </Hoja>
      )}
    </div>
  )
}

const marca = () => window.history.state?.__hoja

describe('Hoja', () => {
  it('es un diálogo modal accesible y registra una entrada de historial', async () => {
    render(<Demo />)
    await userEvent.click(screen.getByText('Abrir'))
    const dialogo = screen.getByRole('dialog', { name: 'Nueva meta' })
    expect(dialogo).toHaveAttribute('aria-modal', 'true')
    expect(marca()).toBeTruthy()
    // el foco entra a la hoja
    expect(dialogo.contains(document.activeElement)).toBe(true)
  })

  it('Escape cierra la hoja y devuelve el foco al botón que la abrió', async () => {
    const alCerrar = vi.fn()
    render(<Demo onCerrarExterno={alCerrar} />)
    const abrir = screen.getByText('Abrir')
    await userEvent.click(abrir)
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(alCerrar).toHaveBeenCalledTimes(1)
    // El foco vuelve un instante después de que desaparece la hoja: se espera, no se mide de golpe.
    await waitFor(() => expect(abrir).toHaveFocus())
    // y su entrada de historial se retira
    await waitFor(() => expect(marca()).toBeFalsy())
  })

  it('atrás (popstate) cierra la hoja sin salir de la pantalla', async () => {
    const alCerrar = vi.fn()
    render(<Demo onCerrarExterno={alCerrar} />)
    await userEvent.click(screen.getByText('Abrir'))
    expect(marca()).toBeTruthy()
    act(() => {
      window.history.back()
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(alCerrar).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Abrir')).toBeInTheDocument()
    expect(marca()).toBeFalsy()
  })

  it('tocar fuera cierra, tocar dentro no', async () => {
    render(<Demo />)
    await userEvent.click(screen.getByText('Abrir'))
    const dialogo = screen.getByRole('dialog')
    await userEvent.click(dialogo)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    const fondo = dialogo.parentElement
    fireEvent.pointerDown(fondo)
    fireEvent.click(fondo)
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('el botón interno usa cerrar() con animación de salida', async () => {
    render(<Demo />)
    await userEvent.click(screen.getByText('Abrir'))
    await userEvent.click(screen.getByText('Cerrar hoja'))
    expect(screen.getByRole('dialog').parentElement.className).toContain('hoja-saliendo')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('una X que cierra desde el padre (sin cerrar()) también anima la salida', async () => {
    function ConX() {
      const [abierta, setAbierta] = useState(true)
      return (
        abierta && (
          <Hoja titulo="Con X" onCerrar={() => setAbierta(false)} testId="hoja-x">
            <button aria-label="Cerrar" onClick={() => setAbierta(false)}>
              X
            </button>
          </Hoja>
        )
      )
    }
    globalThis.__hojaFantasma = true
    render(<ConX />)
    await userEvent.click(screen.getByLabelText('Cerrar'))
    globalThis.__hojaFantasma = false
    // Para lectores de pantalla y pruebas la hoja ya no existe…
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    // …pero queda una copia inerte reproduciendo la salida, que luego se retira
    const fantasma = document.querySelector('.hoja-fantasma')
    expect(fantasma).toBeInTheDocument()
    expect(fantasma).toHaveClass('hoja-saliendo')
    expect(fantasma).toHaveAttribute('aria-hidden', 'true')
    await waitFor(() => expect(document.querySelector('.hoja-fantasma')).not.toBeInTheDocument())
  })

  it('la duración de salida sale de los tokens y coincide con el CSS', async () => {
    const { DURACION_SALIDA } = await import('../components/Hoja')
    const { DUR_MS } = await import('../lib/tokens')
    const fs = await import('node:fs')
    const css = fs.readFileSync(`${process.cwd()}/src/index.css`, 'utf8')
    expect(DURACION_SALIDA).toBe(DUR_MS.normal)
    expect(css).toMatch(new RegExp(`--dur-normal:\\s*${DUR_MS.normal}ms`))
    expect(css).toMatch(new RegExp(`--dur-rapido:\\s*${DUR_MS.rapido}ms`))
    expect(css).toMatch(new RegExp(`--dur-lento:\\s*${DUR_MS.lento}ms`))
  })

  it('la trampa de foco mantiene Tab dentro de la hoja', async () => {
    render(<Demo />)
    await userEvent.click(screen.getByText('Abrir'))
    const dialogo = screen.getByRole('dialog')
    await userEvent.tab()
    await userEvent.tab()
    await userEvent.tab()
    await userEvent.tab()
    expect(dialogo.contains(document.activeElement)).toBe(true)
    await userEvent.tab({ shift: true })
    expect(dialogo.contains(document.activeElement)).toBe(true)
  })

  it('con dos hojas apiladas, Escape solo cierra la de arriba', async () => {
    function Doble() {
      const [a, setA] = useState(true)
      const [b, setB] = useState(true)
      return (
        <>
          {a && (
            <Hoja titulo="Abajo" onCerrar={() => setA(false)}>
              <p>uno</p>
            </Hoja>
          )}
          {b && (
            <Hoja titulo="Arriba" onCerrar={() => setB(false)}>
              <p>dos</p>
            </Hoja>
          )}
        </>
      )
    }
    render(<Doble />)
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Arriba' })).not.toBeInTheDocument())
    expect(screen.getByRole('dialog', { name: 'Abajo' })).toBeInTheDocument()
  })
})

describe('Hoja dentro de una pantalla animada', () => {
  it('se monta en document.body, no dentro del contenedor con transform', async () => {
    render(
      <div className="screen-enter" data-testid="pantalla">
        <Demo />
      </div>
    )
    await userEvent.click(screen.getByText('Abrir'))
    const dialogo = screen.getByRole('dialog', { name: 'Nueva meta' })
    expect(screen.getByTestId('pantalla').contains(dialogo)).toBe(false)
    expect(dialogo.closest('.hoja-fondo').parentElement).toBe(document.body)
  })

  it('.screen-enter y .stagger-item no dejan fill-mode both/forwards (transform permanente)', async () => {
    const fs = await import('node:fs')
    const css = fs.readFileSync(`${process.cwd()}/src/index.css`, 'utf8')
    for (const clase of ['screen-enter', 'stagger-item']) {
      const bloque = css.match(new RegExp(`\\.${clase}\\s*\\{[^}]*\\}`))[0].replace(/\/\*[\s\S]*?\*\//g, '')
      expect(bloque).not.toMatch(/\b(both|forwards)\b/)
    }
  })
})
