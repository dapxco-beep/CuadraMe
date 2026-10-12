// «Lo que te cuesta tu plata»: pantalla /costos, tarjeta de Inicio, enlaces y glosario.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({
  api: new Proxy(api, { get: (t, nombre) => t[nombre] ?? (() => Promise.resolve([])) }),
}))
vi.mock('../lib/BloqueoContext', () => ({
  useBloqueo: () => ({ fmt: (n) => `$${Math.round(n).toLocaleString('es-CO')}`, oculto: false }),
}))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import Costos from '../screens/Costos'
import EnlaceCostos from '../components/EnlaceCostos'
import TarjetaCostos from '../components/TarjetaCostos'
import { GLOSARIO, LECCIONES } from '../lib/aprende'
import { barrasPorTipo, hayCostos, textoVariacion } from '../lib/costos'

const BLOQUE = { intereses: 120000, cuota: 28000, comisiones: 15000, gmf: 8000, rendimientos: 60000, total: 171000, costo_neto: 111000 }
const DATOS = {
  aviso: 'Orientación educativa, no es asesoría financiera.',
  tiene_datos: true,
  anio: { anio: 2026, ...BLOQUE, total: 900000, costo_neto: 700000, rendimientos: 200000 },
  mes: { mes: '2026-10', ...BLOQUE, mes_anterior_total: 150000, variacion_pct: 14 },
  promedio_mensual: 140000,
  meses: [
    { mes: '2026-08', total: 100000 }, { mes: '2026-09', total: 150000 }, { mes: '2026-10', total: 171000 },
  ],
  por_cuenta: [{ cuenta_id: 'v', nombre: 'Visa Nu', total: 150000 }],
  alertas: [
    { id: 'costos-mora:v:2026-10', tipo: 'mora', prioridad: 1, titulo: 'Pagaste intereses de mora en Visa Nu', texto: 'Te cobraron $45.000 por mora.', cifra: '$45.000', accion: { texto: 'Ver mi tarjeta', ruta: '/cuentas' } },
  ],
  suscripciones: { lista: [{ huella: 'netflix', nombre: 'Netflix', monto: 29900, subio: false }, { huella: 'gym', nombre: 'Gym', monto: 90000, subio: true }], total_mensual: 119900 },
}

function montar(ui) {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  for (const k of Object.keys(api)) delete api[k]
})

describe('lib/costos', () => {
  it('hayCostos ignora respuestas vacías, listas y sin cobros', () => {
    expect(hayCostos(null)).toBe(false)
    expect(hayCostos([])).toBe(false)
    expect(hayCostos({ tiene_datos: false })).toBe(false)
    expect(hayCostos({ tiene_datos: true, anio: { total: 0 }, mes: { total: 0 } })).toBe(false)
    expect(hayCostos(DATOS)).toBe(true)
  })

  it('barras por tipo en proporción a la más grande y texto de variación llano', () => {
    const b = barrasPorTipo(BLOQUE)
    expect(b.map((x) => x.clave)).toEqual(['intereses', 'cuota', 'comisiones', 'gmf'])
    expect(b[0].pct).toBe(100)
    expect(b[3].pct).toBe(7)
    expect(textoVariacion({ variacion_pct: 14 })).toBe('Subió 14 % frente al mes pasado.')
    expect(textoVariacion({ variacion_pct: -5 })).toBe('Bajó 5 % frente al mes pasado.')
    expect(textoVariacion({ variacion_pct: null })).toMatch(/Aún no hay/)
  })

  it('el glosario trae los términos pedidos y todos apuntan a lecciones reales', () => {
    for (const id of ['intereses-de-mora', 'cuota-de-manejo', '4x1000', 'seguro-de-deudores', 'costo-neto']) {
      const t = GLOSARIO.find((x) => x.id === id)
      expect(t, id).toBeTruthy()
      expect(LECCIONES.some((l) => l.id === t.leccion), id).toBe(true)
    }
  })
})

describe('Pantalla /costos', () => {
  it('muestra la cifra del año y del mes, barras por tipo, alertas y suscripciones', async () => {
    api.costosBancarios = vi.fn().mockResolvedValue(DATOS)
    montar(<Costos />)
    expect(await screen.findByTestId('costo-anio')).toHaveTextContent('$900.000')
    expect(screen.getByTestId('costo-mes')).toHaveTextContent('$171.000')
    expect(screen.getByText('Subió 14 % frente al mes pasado.')).toBeInTheDocument()
    expect(screen.getByTestId('costo-neto')).toHaveTextContent('$700.000')
    for (const n of ['Intereses de tarjeta', 'Cuota de manejo', 'Comisiones y seguros', '4x1000 (GMF)']) {
      expect(screen.getAllByText(n).length).toBeGreaterThan(0)
    }
    expect(screen.getAllByRole('progressbar').length).toBeGreaterThanOrEqual(4)
    expect(screen.getByTestId('alerta-costos')).toHaveTextContent('intereses de mora')
    expect(screen.getByTestId('suscripciones')).toHaveTextContent('Tus suscripciones: $119.900 al mes')
    expect(screen.getByText(/no es asesoría financiera/i)).toBeInTheDocument()
  })

  it('una alerta descartada no vuelve a salir', async () => {
    api.costosBancarios = vi.fn().mockResolvedValue(DATOS)
    const u = userEvent.setup()
    const { unmount } = montar(<Costos />)
    await u.click(await screen.findByRole('button', { name: /Descartar alerta/ }))
    expect(screen.queryByTestId('alerta-costos')).not.toBeInTheDocument()
    unmount()
    montar(<Costos />)
    await screen.findByTestId('costo-anio')
    expect(screen.queryByTestId('alerta-costos')).not.toBeInTheDocument()
  })

  it('cambia las barras entre este mes y este año', async () => {
    api.costosBancarios = vi.fn().mockResolvedValue({ ...DATOS, mes: { ...DATOS.mes, intereses: 10000, cuota: 0, comisiones: 0, gmf: 0 } })
    const u = userEvent.setup()
    montar(<Costos />)
    await screen.findByTestId('costo-anio')
    await u.click(screen.getByRole('button', { name: 'Este mes' }))
    expect(screen.getByRole('button', { name: 'Este mes' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getAllByText('$10.000').length).toBeGreaterThan(0)
  })

  it('estado vacío amable con Cuadri y sin cifras inventadas', async () => {
    api.costosBancarios = vi.fn().mockResolvedValue({ tiene_datos: false })
    montar(<Costos />)
    expect(await screen.findByText('Cuando traigas un extracto con intereses o comisiones, te lo muestro aquí.')).toBeInTheDocument()
    expect(screen.queryByTestId('costo-anio')).not.toBeInTheDocument()
  })

  it('si falla la carga muestra el error en español', async () => {
    api.costosBancarios = vi.fn().mockRejectedValue(new Error('Sin conexión'))
    montar(<Costos />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión')
  })
})

describe('Enlaces y tarjeta', () => {
  it('el enlace y la tarjeta de Inicio solo aparecen con datos', async () => {
    api.costosBancarios = vi.fn().mockResolvedValue({ tiene_datos: false })
    const { unmount } = montar(<><EnlaceCostos /><TarjetaCostos /></>)
    await waitFor(() => expect(api.costosBancarios).toHaveBeenCalled())
    expect(screen.queryByTestId('enlace-costos')).not.toBeInTheDocument()
    expect(screen.queryByTestId('tarjeta-costos')).not.toBeInTheDocument()
    unmount()

    api.costosBancarios = vi.fn().mockResolvedValue(DATOS)
    montar(<><EnlaceCostos /><TarjetaCostos /></>)
    const enlace = await screen.findByTestId('enlace-costos')
    expect(enlace).toHaveAttribute('href', '/costos')
    const tarjeta = await screen.findByTestId('tarjeta-costos')
    expect(within(tarjeta).getByText('$171.000')).toBeInTheDocument()
    expect(tarjeta).toHaveTextContent('Hay un cobro por revisar.')
  })
})
