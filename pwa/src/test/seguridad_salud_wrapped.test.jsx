import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
const logout = vi.hoisted(() => vi.fn())
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({ usuario: { id: 'u1', email: 'l@test.com', nombre: 'Laura' }, logout }),
}))

import { BloqueoProvider, useBloqueo } from '../lib/BloqueoContext'
import PantallaBloqueo from '../components/PantallaBloqueo'
import BotonOjo from '../components/BotonOjo'
import TarjetaSalud from '../components/TarjetaSalud'
import Wrapped from '../screens/Wrapped'
import { DialogosProvider } from '../lib/DialogosContext'
import * as seg from '../lib/seguridad'
import { construirDiapositivas, nombreMes } from '../lib/wrappedImagen'

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})

describe('seguridad.js', () => {
  it('guarda solo el hash del PIN y lo verifica', async () => {
    await seg.guardarPin('4821')
    const guardado = localStorage.getItem('cuadrame_pin')
    expect(guardado).not.toContain('4821')
    expect(await seg.verificarPin('4821')).toBe(true)
    expect(await seg.verificarPin('1111')).toBe(false)
  })

  it('rechaza PIN inválidos', async () => {
    expect(seg.pinValido('123')).toBe(false)
    expect(seg.pinValido('1234567')).toBe(false)
    expect(seg.pinValido('12a4')).toBe(false)
    expect(seg.pinValido('123456')).toBe(true)
    await expect(seg.guardarPin('12')).rejects.toThrow()
  })

  it('tras 5 fallos impone espera', () => {
    for (let i = 0; i < 4; i++) expect(seg.registrarFallo().espera).toBe(0)
    expect(seg.registrarFallo().espera).toBe(15)
    expect(seg.estadoIntentos().espera).toBeGreaterThan(0)
    seg.limpiarFallos()
    expect(seg.estadoIntentos().espera).toBe(0)
  })

  it('borrarSeguridad elimina PIN, biometría y ajustes; conserva ocultar saldos', async () => {
    await seg.guardarPin('1234')
    seg.guardarMinutosBloqueo(15)
    seg.guardarOcultarSaldos(true)
    seg.borrarSeguridad()
    expect(seg.tienePin()).toBe(false)
    expect(seg.minutosBloqueo()).toBe(seg.BLOQUEO_POR_DEFECTO)
    expect(seg.leerOcultarSaldos()).toBe(true)
  })

  it('no revienta si localStorage lanza', () => {
    const espia = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })
    expect(seg.tienePin()).toBe(false)
    expect(seg.leerOcultarSaldos()).toBe(false)
    espia.mockRestore()
  })
})

function Sonda() {
  const { bloqueado, fmt } = useBloqueo()
  return <p>{bloqueado ? 'BLOQUEADA' : `libre ${fmt(1500000)}`}</p>
}

describe('bloqueo y ocultar saldos', () => {
  it('con PIN la app arranca bloqueada y el PIN correcto desbloquea', async () => {
    await seg.guardarPin('2580')
    function App() {
      const { bloqueado } = useBloqueo()
      return bloqueado ? <PantallaBloqueo /> : <p>contenido</p>
    }
    render(<BloqueoProvider><App /></BloqueoProvider>)
    expect(screen.getByText('CuadraMe está bloqueada')).toBeInTheDocument()
    for (const d of ['1', '1', '1', '1']) await userEvent.click(screen.getByRole('button', { name: d }))
    await userEvent.click(screen.getByText('Entrar'))
    expect(await screen.findByText('PIN incorrecto')).toBeInTheDocument()
    for (const d of ['2', '5', '8', '0']) await userEvent.click(screen.getByRole('button', { name: d }))
    await userEvent.click(screen.getByText('Entrar'))
    expect(await screen.findByText('contenido')).toBeInTheDocument()
  })

  it('bloquea al volver tras más tiempo del configurado en segundo plano', async () => {
    await seg.guardarPin('2580')
    seg.guardarMinutosBloqueo(5)
    function App() {
      const { bloqueado, desbloquear } = useBloqueo()
      return <><Sonda /><button onClick={desbloquear}>abrir</button>{bloqueado && <i>x</i>}</>
    }
    render(<BloqueoProvider><App /></BloqueoProvider>)
    await userEvent.click(screen.getByText('abrir'))
    expect(screen.getByText(/libre/)).toBeInTheDocument()

    const ahora = Date.now()
    const reloj = vi.spyOn(Date, 'now')
    const visibilidad = vi.spyOn(document, 'visibilityState', 'get')
    visibilidad.mockReturnValue('hidden')
    reloj.mockReturnValue(ahora)
    fireEvent(document, new Event('visibilitychange'))
    // 2 min: no bloquea
    visibilidad.mockReturnValue('visible')
    reloj.mockReturnValue(ahora + 2 * 60_000)
    fireEvent(document, new Event('visibilitychange'))
    expect(screen.getByText(/libre/)).toBeInTheDocument()
    // 6 min: sí bloquea
    visibilidad.mockReturnValue('hidden')
    reloj.mockReturnValue(ahora)
    fireEvent(document, new Event('visibilitychange'))
    visibilidad.mockReturnValue('visible')
    reloj.mockReturnValue(ahora + 6 * 60_000)
    fireEvent(document, new Event('visibilitychange'))
    expect(await screen.findByText('BLOQUEADA')).toBeInTheDocument()
    reloj.mockRestore()
    visibilidad.mockRestore()
  })

  it('el ojo enmascara los montos y recuerda la preferencia', async () => {
    render(<BloqueoProvider><BotonOjo /><Sonda /></BloqueoProvider>)
    expect(screen.getByText(/libre.*1\.500\.000/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Ocultar saldos' }))
    expect(screen.getByText('libre ••••')).toBeInTheDocument()
    expect(localStorage.getItem('cuadrame_ocultar_saldos')).toBe('1')
  })
})

describe('TarjetaSalud', () => {
  it('muestra puntaje, desglose y consejos', async () => {
    api.saludFinanciera = vi.fn().mockResolvedValue({
      score: 72, nivel: 'Buena',
      componentes: [
        { clave: 'emergencia', nombre: 'Fondo de emergencia', puntaje: 50, peso: 50, disponible: true },
        { clave: 'presupuesto', nombre: 'Cumplimiento de presupuesto', puntaje: null, peso: 0, disponible: false },
      ],
      consejos: ['Crea una meta de ahorro'],
    })
    render(<TarjetaSalud />)
    expect(await screen.findByText('72')).toBeInTheDocument()
    expect(screen.getByText('Buena')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Ver desglose'))
    expect(screen.getByText('Fondo de emergencia')).toBeInTheDocument()
    expect(screen.getByText('Sin datos aún')).toBeInTheDocument()
  })

  it('no aparece si el endpoint falla', async () => {
    api.saludFinanciera = vi.fn().mockRejectedValue(new Error('x'))
    const { container } = render(<TarjetaSalud />)
    await waitFor(() => expect(api.saludFinanciera).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})

const DATOS = {
  mes: '2026-09', gasto_total: 1000000, ingresos: 3000000, ahorro: 2000000, tasa_ahorro: 66.7,
  categoria_top: { categoria: 'Mercado', monto: 800000 }, mejor_racha: 3, num_movimientos: 4,
  gasto_mes_anterior: 500000, variacion_gasto_pct: 100,
}

describe('Wrapped', () => {
  it('construye las diapositivas con comparación', () => {
    const d = construirDiapositivas(DATOS)
    expect(d.map((s) => s.id)).toEqual(['gasto', 'categoria', 'ahorro', 'racha', 'comparacion'])
    expect(d[1].valor).toBe('Mercado')
    expect(d[4].valor).toContain('100 %')
    expect(nombreMes('2026-09')).toBe('Septiembre')
  })

  it('mes sin datos previos no inventa comparación', () => {
    const d = construirDiapositivas({ ...DATOS, variacion_gasto_pct: null, categoria_top: null, num_movimientos: 0 })
    expect(d[4].valor).toBe('—')
    expect(d[1].valor).toBe('Sin gastos')
  })

  it('navega entre diapositivas y comparte (con descarga de respaldo)', async () => {
    api.wrapped = vi.fn().mockResolvedValue(DATOS)
    api.informeMeses = vi.fn().mockResolvedValue({ meses: [], ultimo_con_datos: null })
    // jsdom no implementa canvas: se simula lo mínimo para generar el PNG
    const ctx = new Proxy({}, { get: (_, p) => (p === 'createLinearGradient' ? () => ({ addColorStop() {} }) : () => {}), set: () => true })
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx)
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((cb) => cb(new Blob(['x'], { type: 'image/png' })))
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    render(
      <DialogosProvider>
        <MemoryRouter><Wrapped /></MemoryRouter>
      </DialogosProvider>
    )
    expect(await screen.findByText(/1\.000\.000/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Diapositiva siguiente' }))
    expect(await screen.findByText('Mercado')).toBeInTheDocument()

    await userEvent.click(screen.getByText(/Compartir mi Septiembre/))
    await waitFor(() => expect(clic).toHaveBeenCalled())
  })
})
