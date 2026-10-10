// Recorrido guiado de bienvenida, crear cuenta guiado por banco (ahorros vs tarjeta) y atajos por enlace.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const api = vi.hoisted(() => ({
  crearCuenta: vi.fn(async (d) => ({ id: 'x', ...d })),
  apiKey: vi.fn(),
  regenerarApiKey: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => ({ usuario: { id: 'u1', email: 'a@b.co', nombre: 'Ana' } }) }))

import Recorrido from '../components/Recorrido'
import RecorridoEntrada from '../components/RecorridoEntrada'
import CrearCuenta from '../screens/CrearCuenta'
import {
  acotar, debeAbrirseSolo, guardarRecorrido, leerRecorrido, marcarRecorridoPendiente, PASOS_RECORRIDO, porcentajeRecorrido,
  rutaDelPaso, sePuedeRetomar, TOTAL_PASOS,
} from '../lib/recorrido'
import { nombreCortoBanco, productoAlterno, textoAgregarAlterno } from '../lib/cuentaNueva'

function Donde() {
  const l = useLocation()
  return <p data-testid="ruta">{l.pathname + l.search}</p>
}
const montar = (ui, ruta = '/') =>
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="*" element={<>{ui}<Donde /></>} />
      </Routes>
    </MemoryRouter>
  )

beforeEach(() => {
  localStorage.clear()
  api.crearCuenta.mockClear()
  api.apiKey.mockReset().mockResolvedValue({ api_key: 'cm_k' })
})

describe('recorrido: reglas puras', () => {
  it('tiene un paso por área, con ruta, texto corto e ilustración', () => {
    expect(PASOS_RECORRIDO.map((p) => p.id)).toEqual([
      'inicio', 'cuentas', 'traer', 'movimientos', 'presupuesto', 'metas', 'informes', 'asistente', 'privacidad',
    ])
    for (const p of PASOS_RECORRIDO) {
      expect(p.ruta).toMatch(/^\//)
      expect(p.texto.length).toBeLessThan(260)
      expect(p.accion).toBeTruthy()
    }
    const cuentas = PASOS_RECORRIDO.find((p) => p.id === 'cuentas')
    expect(cuentas.texto).toMatch(/tarjeta resta/)
    expect(cuentas.detalle).toMatch(/Nu/)
    expect(cuentas.detalle).toMatch(/corte/)
    expect(PASOS_RECORRIDO.find((p) => p.id === 'movimientos').detalle).toMatch(/traslado/)
  })

  it('acota el índice y calcula el avance', () => {
    expect(acotar(-4)).toBe(0)
    expect(acotar(99)).toBe(TOTAL_PASOS - 1)
    expect(acotar('x')).toBe(0)
    expect(porcentajeRecorrido(TOTAL_PASOS - 1)).toBe(100)
    expect(rutaDelPaso(1)).toBe('/cuentas')
  })

  it('una cuenta nueva abre solo; terminado o saltado ya no; a medias se puede retomar', () => {
    expect(debeAbrirseSolo(leerRecorrido('u1'))).toBe(false) // cuentas viejas: nunca solo
    marcarRecorridoPendiente('u1')
    expect(debeAbrirseSolo(leerRecorrido('u1'))).toBe(true)
    guardarRecorrido('u1', { pendiente: false, empezado: true, paso: 3 })
    expect(debeAbrirseSolo(leerRecorrido('u1'))).toBe(false)
    expect(sePuedeRetomar(leerRecorrido('u1'))).toBe(true)
    guardarRecorrido('u1', { saltado: true })
    expect(sePuedeRetomar(leerRecorrido('u1'))).toBe(false)
    expect(leerRecorrido('otra').paso).toBe(0) // cada persona su propio avance
  })
})

describe('Recorrido (pantalla completa)', () => {
  it('es un diálogo accesible con el primer paso y el avance', () => {
    montar(<Recorrido onCerrar={() => {}} />)
    const dialogo = screen.getByRole('dialog')
    expect(dialogo).toHaveAttribute('aria-modal', 'true')
    expect(within(dialogo).getByRole('heading', { name: 'Tu plata de un vistazo' })).toHaveFocus()
    expect(screen.getByTestId('recorrido-avance')).toHaveTextContent('Paso 1 de 9 · Inicio')
    expect(screen.getByRole('progressbar', { name: 'Avance del recorrido' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Atrás/ })).toBeDisabled()
  })

  it('avanza con el botón, con las flechas del teclado y con los puntos; recuerda el paso', async () => {
    montar(<Recorrido onCerrar={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /Siguiente: Cuentas/ }))
    expect(screen.getByRole('heading', { name: 'Cuentas: débito o tarjeta' })).toBeInTheDocument()
    expect(leerRecorrido('u1').paso).toBe(1)
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'ArrowRight' })
    expect(screen.getByTestId('recorrido-avance')).toHaveTextContent('Paso 3 de 9 · Traer movimientos')
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'ArrowLeft' })
    expect(screen.getByTestId('recorrido-avance')).toHaveTextContent('Paso 2 de 9')
    await userEvent.click(screen.getByRole('button', { name: 'Ir al paso 9: Privacidad' }))
    expect(screen.getByRole('button', { name: 'Ir al paso 9: Privacidad' })).toHaveAttribute('aria-current', 'step')
    expect(leerRecorrido('u1').paso).toBe(8)
  })

  it('Cuentas explica débito vs tarjeta y despliega el ejemplo de Nu', async () => {
    montar(<Recorrido desde={1} onCerrar={() => {}} />)
    expect(screen.getByText(/la tarjeta resta/)).toBeInTheDocument()
    expect(screen.queryByText(/cupo de \$2\.000\.000/)).toBeNull()
    const ver = screen.getByRole('button', { name: /Ver un ejemplo/ })
    expect(ver).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(ver)
    expect(ver).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText(/cupo de \$2\.000\.000/)).toBeInTheDocument()
  })

  it('«Probar ahora» lleva a la pantalla del paso y deja guardado dónde iba', async () => {
    const cerrar = vi.fn()
    montar(<Recorrido desde={4} onCerrar={cerrar} />)
    await userEvent.click(screen.getByRole('button', { name: 'Probar ahora' }))
    expect(screen.getByTestId('ruta')).toHaveTextContent('/presupuesto')
    expect(cerrar).toHaveBeenCalledWith('probar')
    expect(leerRecorrido('u1')).toMatchObject({ paso: 4, empezado: true, saltado: false, terminado: false })
  })

  it('se puede saltar, cerrar con Escape (retomable) y terminar en el último paso', async () => {
    const cerrar = vi.fn()
    const { unmount } = montar(<Recorrido desde={2} onCerrar={cerrar} />)
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(cerrar).toHaveBeenLastCalledWith('luego')
    expect(sePuedeRetomar(leerRecorrido('u1'))).toBe(true)
    unmount()

    const cerrar2 = vi.fn()
    const r2 = montar(<Recorrido desde={2} onCerrar={cerrar2} />)
    await userEvent.click(screen.getByRole('button', { name: /Saltar recorrido/ }))
    expect(cerrar2).toHaveBeenCalledWith('saltado')
    expect(leerRecorrido('u1').saltado).toBe(true)
    r2.unmount()

    const cerrar3 = vi.fn()
    montar(<Recorrido desde={TOTAL_PASOS - 1} onCerrar={cerrar3} />)
    expect(screen.queryByRole('button', { name: /^Siguiente/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Terminar y empezar' }))
    expect(cerrar3).toHaveBeenCalledWith('terminado')
    expect(leerRecorrido('u1').terminado).toBe(true)
  })

  it('las ilustraciones son decorativas para el lector de pantalla', () => {
    montar(<Recorrido desde={1} onCerrar={() => {}} />)
    const svg = screen.getByRole('dialog').querySelector('main svg')
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg.textContent).toMatch(/TARJETA DE CRÉDITO/)
    expect(svg.textContent).toMatch(/DÉBITO/)
  })
})

describe('RecorridoEntrada', () => {
  it('en Inicio abre solo si la cuenta es nueva, y no se repite', () => {
    const { unmount } = montar(<RecorridoEntrada variante="inicio" />)
    expect(screen.queryByRole('dialog')).toBeNull()
    unmount()
    marcarRecorridoPendiente('u1')
    const r = montar(<RecorridoEntrada variante="inicio" />)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    r.unmount()
    montar(<RecorridoEntrada variante="inicio" />)
    expect(screen.queryByRole('dialog')).toBeNull() // ya empezó: no vuelve a abrirse solo
  })

  it('a medias muestra «Sigue con tu recorrido» y continúa donde iba', async () => {
    guardarRecorrido('u1', { empezado: true, paso: 3 })
    montar(<RecorridoEntrada variante="inicio" />)
    const tarjeta = screen.getByTestId('recorrido-retomar')
    expect(tarjeta).toHaveTextContent('paso 4 de 9')
    await userEvent.click(within(tarjeta).getByRole('button', { name: /Continuar/ }))
    expect(screen.getByTestId('recorrido-avance')).toHaveTextContent('Paso 4 de 9 · Movimientos')
  })

  it('desde Perfil/Ayuda se ve otra vez desde el principio y al terminar vuelve a Inicio', async () => {
    guardarRecorrido('u1', { empezado: true, terminado: true, paso: 8 })
    montar(<RecorridoEntrada />, '/perfil')
    await userEvent.click(screen.getByRole('button', { name: /Ver recorrido otra vez/ }))
    expect(screen.getByTestId('recorrido-avance')).toHaveTextContent('Paso 1 de 9')
    await userEvent.click(screen.getByRole('button', { name: 'Ir al paso 9: Privacidad' }))
    await userEvent.click(screen.getByRole('button', { name: 'Terminar y empezar' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByTestId('ruta')).toHaveTextContent(/^\/$/)
  })
})

describe('Crear cuenta guiado', () => {
  async function hastaPregunta() {
    montar(<CrearCuenta onCreada={vi.fn()} />)
    await userEvent.click(screen.getByText(/Empezar/))
  }

  it('al elegir un banco pregunta si es ahorros/débito o tarjeta, con una línea de cada una', async () => {
    await hastaPregunta()
    expect(screen.queryByTestId('pregunta-producto')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /Nu Colombia/ }))
    const pregunta = screen.getByTestId('pregunta-producto')
    expect(within(pregunta).getByText('¿Es tu cuenta de ahorros/débito o tu tarjeta de crédito?')).toBeInTheDocument()
    expect(within(pregunta).getByText(/ya tienes: cada pago se descuenta/)).toBeInTheDocument()
    expect(within(pregunta).getByText(/plata del banco y la devuelves después/)).toBeInTheDocument()
  })

  it('si es tarjeta pide cupo, corte y pago con ayuda de dónde encontrarlos', async () => {
    await hastaPregunta()
    await userEvent.click(screen.getByRole('button', { name: /Nu Colombia/ }))
    await userEvent.click(within(screen.getByTestId('pregunta-producto')).getByRole('button', { name: /Mi tarjeta de crédito/ }))
    expect(screen.getByLabelText('Nombre de la cuenta')).toHaveValue('Nu Colombia Crédito')
    expect(screen.getByLabelText('Cupo total')).toBeInTheDocument()
    expect(screen.getByLabelText('Día de corte')).toBeInTheDocument()
    expect(screen.getByLabelText('Día de pago')).toBeInTheDocument()
    expect(screen.getAllByText(/app de tu banco/).length).toBeGreaterThanOrEqual(2)
  })

  it('tras crear la tarjeta ofrece agregar también la cuenta de ahorros del mismo banco y no insiste dos veces', async () => {
    const onCreada = vi.fn()
    montar(<CrearCuenta onCreada={onCreada} />)
    await userEvent.click(screen.getByText(/Empezar/))
    await userEvent.click(screen.getByRole('button', { name: /Nu Colombia/ }))
    await userEvent.click(within(screen.getByTestId('pregunta-producto')).getByRole('button', { name: /Mi tarjeta de crédito/ }))
    await userEvent.type(screen.getByLabelText('Cupo total'), '2.000.000')
    await userEvent.type(screen.getByLabelText('Día de corte'), '15')
    await userEvent.type(screen.getByLabelText('Día de pago'), '30')
    await userEvent.click(screen.getByText('Continuar'))

    await waitFor(() =>
      expect(api.crearCuenta).toHaveBeenCalledWith(
        expect.objectContaining({ nombre: 'Nu Colombia Crédito', tipo: 'credito', cupo_total: 2000000, dia_corte: 15, dia_pago: 30 })
      )
    )
    expect(onCreada).not.toHaveBeenCalled() // primero se ofrece la otra
    const boton = await screen.findByRole('button', { name: 'Agregar también mi cuenta de ahorros Nu' })
    await userEvent.click(boton)

    // vuelve al formulario con el mismo banco y la cuenta de ahorros elegida
    expect(screen.getByLabelText('Nombre de la cuenta')).toHaveValue('Nu Colombia')
    expect(within(screen.getByTestId('pregunta-producto')).getByRole('button', { name: /Mi cuenta de ahorros/ })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByText('Continuar'))
    await waitFor(() => expect(api.crearCuenta).toHaveBeenCalledTimes(2))
    expect(api.crearCuenta).toHaveBeenLastCalledWith(expect.objectContaining({ nombre: 'Nu Colombia', tipo: 'ahorro' }))
    await waitFor(() => expect(onCreada).toHaveBeenCalledTimes(1)) // ya tiene las dos: no vuelve a preguntar
    expect(leerRecorrido('u1').pendiente).toBe(true) // y el recorrido se abrirá en Inicio
  })

  it('«No, continuar» termina sin crear la otra', async () => {
    const onCreada = vi.fn()
    montar(<CrearCuenta onCreada={onCreada} />)
    await userEvent.click(screen.getByText(/Empezar/))
    await userEvent.click(screen.getByRole('button', { name: /Bancolombia/ }))
    await userEvent.click(screen.getByText('Continuar'))
    await userEvent.click(await screen.findByRole('button', { name: 'Agregar también mi tarjeta de crédito Bancolombia' }))
    expect(screen.getByLabelText('Nombre de la cuenta')).toHaveValue('Bancolombia Crédito')
    expect(api.crearCuenta).toHaveBeenCalledTimes(1)
  })

  it('sin banco (efectivo) no pregunta nada y termina directo', async () => {
    const onCreada = vi.fn()
    montar(<CrearCuenta onCreada={onCreada} />)
    await userEvent.click(screen.getByText(/Empezar/))
    await userEvent.click(screen.getByRole('button', { name: /Efectivo/ }))
    expect(screen.queryByTestId('pregunta-producto')).toBeNull()
    await userEvent.click(screen.getByText('Continuar'))
    await waitFor(() => expect(onCreada).toHaveBeenCalledTimes(1))
  })
})

describe('cuentaNueva: la otra cuenta del banco', () => {
  it('nombre corto, producto alterno y texto del botón', () => {
    expect(nombreCortoBanco('Nu Colombia')).toBe('Nu')
    expect(nombreCortoBanco('Bancolombia')).toBe('Bancolombia')
    expect(productoAlterno('ahorro')).toBe('credito')
    expect(productoAlterno('credito')).toBe('ahorro')
    expect(productoAlterno('efectivo')).toBeNull()
    expect(textoAgregarAlterno('Nu Colombia', 'ahorro')).toBe('Agregar también mi tarjeta de crédito Nu')
    expect(textoAgregarAlterno('Nu Colombia', 'credito')).toBe('Agregar también mi cuenta de ahorros Nu')
    expect(textoAgregarAlterno('', 'ahorro')).toBe('')
  })
})
