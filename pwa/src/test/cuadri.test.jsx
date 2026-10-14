// Cuadri, la mascota: sus 6 poses, la preferencia «Mostrar a Cuadri», las frases, las celebraciones
// (una sola vez, descartables) y los lugares donde aparece (recorrido, vacíos, errores).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../lib/AuthContext', () => ({ useAuth: () => ({ usuario: { id: 'u1', email: 'a@b.co' } }) }))

import Cuadri, { POSES_CUADRI } from '../brand/Cuadri'
import CelebracionCuadri from '../brand/CelebracionCuadri'
import ErrorAmable from '../brand/ErrorAmable'
import { CargandoMarca, EstadoVacio } from '../brand/Marca'
import Recorrido from '../components/Recorrido'
import { PASOS_RECORRIDO } from '../lib/recorrido'
import {
  CLAVE_CELEBRADAS, CLAVE_MOSTRAR, FRASES, POSES, POSE_RECORRIDO, frase, guardarMostrarCuadri, leerMostrarCuadri, yaCelebrado,
  conNombre,
} from '../lib/cuadri'

beforeEach(() => {
  localStorage.clear()
  vi.useRealTimers()
})

describe('Cuadri: poses y accesibilidad', () => {
  it.each(POSES)('monta la pose %s', (pose) => {
    const { container } = render(<Cuadri pose={pose} />)
    const svg = container.querySelector('svg.cuadri')
    expect(svg).not.toBeNull()
    expect(svg).toHaveAttribute('data-pose', pose)
    expect(svg.querySelectorAll('*').length).toBeLessThan(40) // SVG ligero
  })

  it('las seis poses de la marca existen y cada una tiene datos', () => {
    expect(POSES).toEqual(['feliz', 'hablando', 'sorprendido', 'preocupado', 'senalando', 'celebrando'])
    expect(Object.keys(POSES_CUADRI)).toEqual(POSES)
  })

  it('es decorativo por defecto y con `titulo` pasa a ser una imagen con nombre', () => {
    const { container, rerender } = render(<Cuadri />)
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByRole('img')).toBeNull()
    rerender(<Cuadri titulo="Cuadri celebra" />)
    expect(screen.getByRole('img', { name: 'Cuadri celebra' })).toBeInTheDocument()
  })

  it('una pose desconocida cae en «feliz» sin romper', () => {
    const { container } = render(<Cuadri pose="inexistente" />)
    expect(container.querySelector('svg')).toHaveAttribute('data-pose', 'feliz')
  })

  it('anima solo si se pide y no hay ahorro de datos', () => {
    const { container, rerender } = render(<Cuadri />)
    expect(container.querySelector('svg')).toHaveClass('cuadri-anima')
    rerender(<Cuadri animar={false} />)
    expect(container.querySelector('svg')).not.toHaveClass('cuadri-anima')
    Object.defineProperty(navigator, 'connection', { value: { saveData: true }, configurable: true })
    rerender(<Cuadri />)
    expect(container.querySelector('svg')).not.toHaveClass('cuadri-anima')
    Object.defineProperty(navigator, 'connection', { value: undefined, configurable: true })
  })

  it('usa variables del tema (claro y oscuro), no colores fijos en el cuerpo', () => {
    const { container } = render(<Cuadri />)
    expect(container.querySelector('.cu-relleno-cuerpo')).not.toBeNull()
    expect(container.querySelector('.cu-relleno-cuerpo').getAttribute('fill')).toBeNull()
  })
})

describe('Preferencia «Mostrar a Cuadri»', () => {
  it('viene activada y se guarda en el dispositivo', () => {
    expect(leerMostrarCuadri()).toBe(true)
    guardarMostrarCuadri(false)
    expect(localStorage.getItem(CLAVE_MOSTRAR)).toBe('0')
    expect(leerMostrarCuadri()).toBe(false)
  })

  it('apagada: Cuadri no se pinta y los vacíos/cargas vuelven a la ilustración de marca', () => {
    guardarMostrarCuadri(false)
    const { container } = render(
      <>
        <Cuadri />
        <EstadoVacio titulo="Nada aún" />
        <CargandoMarca />
      </>
    )
    expect(container.querySelector('svg.cuadri')).toBeNull()
    expect(screen.getByText('Nada aún')).toBeInTheDocument()
  })

  it('encendida: el estado vacío y la carga muestran a Cuadri', () => {
    const { container } = render(
      <>
        <EstadoVacio titulo="Nada aún" pose="feliz" />
        <CargandoMarca texto="Cargando" />
      </>
    )
    expect(container.querySelectorAll('svg.cuadri')).toHaveLength(2)
    expect(container.querySelector('svg.cuadri[data-pose="feliz"]')).not.toBeNull()
    expect(screen.getByRole('status')).toHaveTextContent('Cargando')
  })

  it('al cambiarla, los componentes montados reaccionan', () => {
    const { container } = render(<Cuadri />)
    expect(container.querySelector('svg.cuadri')).not.toBeNull()
    act(() => guardarMostrarCuadri(false))
    expect(container.querySelector('svg.cuadri')).toBeNull()
  })
})

describe('Frases de Cuadri', () => {
  const todas = Object.values(FRASES).flatMap((v) => (Array.isArray(v) ? v : Object.values(v)))

  it('hay frases y son cortas', () => {
    expect(todas.length).toBeGreaterThan(15)
    for (const f of todas) expect(f.length).toBeLessThanOrEqual(90)
  })

  it('incluye las frases de marca', () => {
    expect(FRASES.cuadra).toContain('¡Eso cuadra!')
    expect(FRASES.noCuadra[0]).toBe('Ups, algo no cuadra… lo revisamos juntos.')
  })

  it('tono tierno: nada de culpar, burlarse ni dar asesoría', () => {
    const prohibido = /gastaste de m[aá]s|derrochas|malgast|tonto|culpa|deber[ií]as|invierte en|compra acciones|te garantizamos|rentabilidad asegurada/i
    for (const f of todas) expect(f).not.toMatch(prohibido)
  })

  it('frase() es estable para la misma semilla y tolera claves inexistentes', () => {
    expect(frase('cuadra', 1)).toBe(frase('cuadra', 1))
    expect(frase('cuadra', 'abc')).toBeTruthy()
    expect(frase('no-existe')).toBe('')
  })

  it('cada paso del recorrido tiene frase y pose', () => {
    for (const p of PASOS_RECORRIDO) {
      expect(FRASES.recorrido[p.id], p.id).toBeTruthy()
      expect(POSES).toContain(POSE_RECORRIDO[p.id])
    }
  })
})

describe('Celebración', () => {
  it('sale una sola vez, se puede cerrar y no repite', () => {
    const { rerender } = render(<CelebracionCuadri id="meta-1" titulo="¡Lograste tu meta!" texto="Eso cuadra" />)
    const aviso = screen.getByTestId('celebracion-cuadri')
    expect(aviso).toHaveAttribute('role', 'status')
    expect(aviso).toHaveTextContent('¡Lograste tu meta!')
    expect(aviso.querySelector('svg.cuadri')).toHaveAttribute('data-pose', 'celebrando')
    expect(yaCelebrado('meta-1')).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar aviso' }))
    expect(screen.queryByTestId('celebracion-cuadri')).toBeNull()
    rerender(<CelebracionCuadri id="meta-1" titulo="otra vez" />)
    expect(screen.queryByTestId('celebracion-cuadri')).toBeNull()
  })

  it('se va sola a los 7 segundos', () => {
    vi.useFakeTimers()
    render(<CelebracionCuadri id="mes-1" titulo="Hola" />)
    expect(screen.getByTestId('celebracion-cuadri')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(7100))
    expect(screen.queryByTestId('celebracion-cuadri')).toBeNull()
  })

  it('no sale si la condición no se cumple ni si Cuadri está apagado', () => {
    const { rerender } = render(<CelebracionCuadri id="a" cuando={false} titulo="x" />)
    expect(screen.queryByTestId('celebracion-cuadri')).toBeNull()
    expect(yaCelebrado('a')).toBe(false)
    rerender(<CelebracionCuadri id="a" cuando titulo="x" />)
    expect(screen.getByTestId('celebracion-cuadri')).toBeInTheDocument()
    guardarMostrarCuadri(false)
    render(<CelebracionCuadri id="b" titulo="y" />)
    expect(yaCelebrado('b')).toBe(false)
    expect(localStorage.getItem(CLAVE_CELEBRADAS)).not.toContain('"b"')
  })
})

describe('Error amable', () => {
  it('Cuadri preocupado/sorprendido, texto claro y acción', () => {
    const accion = vi.fn()
    const { container, rerender } = render(<ErrorAmable detalle="Falló algo" onAccion={accion} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Algo no salió bien')
    expect(container.querySelector('svg.cuadri')).toHaveAttribute('data-pose', 'sorprendido')
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(accion).toHaveBeenCalled()
    rerender(<ErrorAmable sinConexion onAccion={accion} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Sin conexión por ahora')
    expect(container.querySelector('svg.cuadri')).toHaveAttribute('data-pose', 'preocupado')
  })
})

describe('Recorrido con Cuadri como guía', () => {
  const montar = () =>
    render(
      <MemoryRouter>
        <Recorrido onCerrar={() => {}} />
      </MemoryRouter>
    )

  it('cambia de pose por paso y celebra al terminar', () => {
    montar()
    const guia = () => screen.getByTestId('recorrido-cuadri')
    expect(guia().querySelector('svg')).toHaveAttribute('data-pose', POSE_RECORRIDO.inicio)
    expect(guia()).toHaveTextContent(conNombre(FRASES.recorrido.inicio, ''))
    fireEvent.click(screen.getByRole('button', { name: /^Siguiente/ }))
    expect(guia().querySelector('svg')).toHaveAttribute('data-pose', 'senalando')
    fireEvent.click(screen.getByRole('button', { name: `Ir al paso ${PASOS_RECORRIDO.length}: ${PASOS_RECORRIDO.at(-1).area}` }))
    expect(guia().querySelector('svg')).toHaveAttribute('data-pose', 'celebrando')
  })

  it('con Cuadri apagado el recorrido sigue igual, sin guía', () => {
    guardarMostrarCuadri(false)
    montar()
    expect(screen.queryByTestId('recorrido-cuadri')).toBeNull()
    expect(screen.getByTestId('recorrido-avance')).toBeInTheDocument()
  })
})
