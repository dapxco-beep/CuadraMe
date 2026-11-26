import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
// Formato de pesos fijo y sin espacios raros, para que las cifras se lean tal cual en las pruebas.
vi.mock('../lib/BloqueoContext', () => ({
  useBloqueo: () => ({ fmt: (v) => `$${Math.abs(Math.round(v)).toLocaleString('es-CO')}` }),
}))

import Panorama from '../screens/Panorama'
import FlujoNeto from '../components/informe/FlujoNeto'
import TasaAhorro from '../components/informe/TasaAhorro'
import PresupuestoReal from '../components/informe/PresupuestoReal'
import { Cambio, enPeriodo } from '../components/informe/comun'
import { destinoHallazgo } from '../components/informe/Hallazgos'

const fmt = (v) => `$${Math.abs(Math.round(v)).toLocaleString('es-CO')}`

// Octubre 1–15 de 2026 (las mismas cifras que las pruebas del servidor, calculadas a mano):
// ingresos 1.200.000, gastos 200.000, flujo neto 1.000.000, tasa de ahorro 83,3 %.
const punto = (dia, ing, gas) => ({
  clave: `2026-10-${String(dia).padStart(2, '0')}`, etiqueta: String(dia), etiqueta_larga: `${dia} de octubre`,
  desde: `2026-10-${String(dia).padStart(2, '0')}`, hasta: `2026-10-${String(dia).padStart(2, '0')}`,
  ingresos: ing, gastos: gas, neto: ing === null ? null : ing - gas, acumulado: 0, con_datos: ing !== null,
})
const PUNTOS = [punto(1, 1_000_000, 0), punto(2, 0, 100_000), punto(3, null, null), punto(5, 200_000, 0), punto(9, 0, 50_000), punto(10, 0, 50_000)]
let acum = 0
PUNTOS.forEach((p) => { if (p.con_datos) acum += p.neto; p.acumulado = acum })

const RESUMEN = {
  desde: '2026-10-01', hasta: '2026-10-15', etiqueta: 'octubre de 2026', periodo: 'este_mes', en_curso: true,
  ingresos: 1_200_000, gastos: 200_000, balance: 1_000_000, tasa_ahorro: 83.3,
  anterior: { desde: '2026-09-01', hasta: '2026-09-15', etiqueta: 'septiembre de 2026', ingresos: 900_000, gastos: 100_000, balance: 800_000, tasa_ahorro: 88.9 },
  variacion: { ingresos_pct: 33.3, gastos_pct: 100, balance_pct: 25, tasa_ahorro_puntos: -5.6 },
  meses: [
    { mes: '2026-08', etiqueta: 'Ago', etiqueta_larga: 'agosto de 2026', ingresos: 0, gastos: 50_000, balance: -50_000, tasa_ahorro: null },
    { mes: '2026-09', etiqueta: 'Sep', etiqueta_larga: 'septiembre de 2026', ingresos: 900_000, gastos: 500_000, balance: 400_000, tasa_ahorro: 44.4 },
    { mes: '2026-10', etiqueta: 'Oct', etiqueta_larga: 'octubre de 2026', ingresos: 1_200_000, gastos: 200_000, balance: 1_000_000, tasa_ahorro: 83.3 },
  ],
  tasa_serie: { promedio: 66.7, meses_con_tasa: 2, mejor: { mes: '2026-10', etiqueta_larga: 'octubre de 2026', tasa_ahorro: 83.3 }, peor: { mes: '2026-09', etiqueta_larga: 'septiembre de 2026', tasa_ahorro: 44.4 } },
  flujo: { agrupar: 'dia', puntos: PUNTOS, positivos: 2, negativos: 3, mejor: '2026-10-01', peor: '2026-10-02', hay_datos: true },
  fuentes: {
    total: 1_200_000, hay_datos: true, otras: null,
    fuentes: [
      { clave: 'sueldo empresa', nombre: 'Sueldo Empresa', categoria: 'Sueldo', monto: 1_000_000, pct: 83.3, num: 1, anterior: 900_000, variacion_pct: 11.1 },
      { clave: 'venta mercado libre', nombre: 'Venta Mercado Libre', categoria: 'Ventas', monto: 200_000, pct: 16.7, num: 1, anterior: 0, variacion_pct: null },
    ],
  },
  presupuesto: {
    hay_presupuestos: true, presupuesto_total: 185_161, gastado_total: 200_000, disponible_total: -14_839, pct_total: 108, gasto_sin_presupuesto: 0, meses_equivalentes: 0.48,
    categorias: [
      { categoria: 'Comida', presupuesto: 145_161, gastado: 150_000, disponible: -4_839, pct: 103.3, estado: 'excedido', alerta_pct: 80 },
      { categoria: 'Transporte', presupuesto: 40_000, gastado: 50_000, disponible: -10_000, pct: 125, estado: 'excedido', alerta_pct: 80 },
    ],
  },
  hallazgos: [
    { id: 'flujo', tono: 'bueno', titulo: 'Tu flujo neto es positivo', texto: 'Entró $1.200.000 y salió $200.000 en octubre de 2026: te sobraron $1.000.000.', enlace: '/informes?tab=panorama', prioridad: 2, datos: {} },
    { id: 'presupuesto_excedido', tono: 'atento', titulo: '2 presupuestos superados', texto: 'Te pasaste en Comida, Transporte.', enlace: '/presupuesto', prioridad: 1, datos: {} },
  ],
  hay_datos: true, moneda_base: 'COP', monedas_sin_tasa: [],
}

const montar = () => render(<MemoryRouter><Panorama /></MemoryRouter>)

beforeEach(() => {
  localStorage.clear()
  api.informeResumen = vi.fn().mockResolvedValue(RESUMEN)
  api.informeMovimientos = vi.fn().mockResolvedValue({ total: 1_000_000, cantidad: 1, movimientos: [{ id: 'm1', fecha: '2026-10-01T08:00:00', descripcion: 'Sueldo Empresa', monto: 1_000_000, categoria: 'Sueldo' }] })
})

describe('Informes > Resumen', () => {
  it('muestra el flujo neto, los tres indicadores y la comparación con el periodo anterior', async () => {
    montar()
    const cifras = await screen.findByRole('region', { name: '¿Me alcanzó la plata?' })
    expect(api.informeResumen).toHaveBeenCalledWith({ periodo: 'este_mes' })
    expect(within(cifras).getByLabelText(/Flujo neto: te sobró \$1\.000\.000/)).toBeInTheDocument()
    const dl = within(cifras).getAllByRole('term').map((t) => t.textContent)
    expect(dl).toEqual(['Ingresos', 'Gastos', 'Tasa de ahorro'])
    expect(within(cifras).getByText('$1.200.000')).toBeInTheDocument()
    expect(within(cifras).getByText('83,3 %')).toBeInTheDocument()
    expect(within(cifras).getByText(/Frente a septiembre de 2026: ingresos \$900\.000, gastos \$100\.000, flujo neto \+\$800\.000, tasa de ahorro 88,9 %/)).toBeInTheDocument()
    // los cambios llevan flecha, signo Y frase (no solo color)
    expect(within(cifras).getByText('sube 33,3 % frente al periodo anterior')).toBeInTheDocument()
    expect(within(cifras).getByText('baja 5,6 puntos frente al periodo anterior')).toBeInTheDocument()
    expect(within(cifras).getByText(/sigue en curso/)).toBeInTheDocument()
    expect(within(cifras).getByRole('link', { name: /Ver los movimientos de este periodo/ })).toHaveAttribute('href', '/movimientos?desde=2026-10-01&hasta=2026-10-15')
  })

  it('cada panel explica cómo se calcula (se abre y se cierra)', async () => {
    const user = userEvent.setup()
    montar()
    const cifras = await screen.findByRole('region', { name: '¿Me alcanzó la plata?' })
    const boton = within(cifras).getByRole('button', { name: /¿Cómo se calcula/ })
    expect(boton).toHaveAttribute('aria-expanded', 'false')
    await user.click(boton)
    expect(boton).toHaveAttribute('aria-expanded', 'true')
    expect(within(cifras).getByText(/Flujo neto: ingresos menos gastos/)).toBeInTheDocument()
    await user.click(boton)
    expect(within(cifras).queryByText(/Flujo neto: ingresos menos gastos/)).toBeNull()
  })

  it('los hallazgos traen su texto con cifras y enlace al detalle', async () => {
    montar()
    const panel = await screen.findByRole('region', { name: 'Lo que dicen tus números' })
    expect(within(panel).getByText('Entró $1.200.000 y salió $200.000 en octubre de 2026: te sobraron $1.000.000.')).toBeInTheDocument()
    const enlaces = within(panel).getAllByRole('link', { name: 'Ver el detalle' })
    expect(enlaces.map((a) => a.getAttribute('href'))).toEqual(['/informes?tab=panorama', '/presupuesto'])
  })

  it('el enlace de un hallazgo conserva el periodo elegido', () => {
    const p = new URLSearchParams('tab=panorama&p=rango&desde=2026-03-01&hasta=2026-03-31')
    expect(destinoHallazgo('/informes?tab=gastos', p)).toBe('/informes?tab=gastos&p=rango&desde=2026-03-01&hasta=2026-03-31')
    expect(destinoHallazgo('/presupuesto', p)).toBe('/presupuesto')
  })

  it('cambiar la agrupación del flujo vuelve a pedir el resumen con esa agrupación', async () => {
    const user = userEvent.setup()
    montar()
    const flujo = await screen.findByRole('region', { name: 'Flujo neto' })
    expect(within(flujo).getByRole('button', { name: 'Día' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(within(flujo).getByRole('button', { name: 'Semana' }))
    await waitFor(() => expect(api.informeResumen).toHaveBeenLastCalledWith({ periodo: 'este_mes', agrupar: 'semana' }))
  })

  it('tocar un ingreso por fuente trae sus movimientos con enlace al detalle', async () => {
    const user = userEvent.setup()
    montar()
    const fuentes = await screen.findByRole('region', { name: 'Ingresos por fuente' })
    expect(within(fuentes).getByText('83,3 %', { exact: false })).toBeInTheDocument()
    await user.click(within(fuentes).getByRole('button', { name: /Sueldo Empresa/ }))
    expect(api.informeMovimientos).toHaveBeenCalledWith({ periodo: 'este_mes', tipo: 'ingreso', fuente: 'sueldo empresa' })
    const link = await within(fuentes).findByRole('link', { name: /Sueldo Empresa/ })
    expect(link).toHaveAttribute('href', '/movimientos/m1')
    // la fuente nueva no tiene base de comparación: se dice, no se inventa
    expect(within(fuentes).getByText('sin base para comparar')).toBeInTheDocument()
  })

  it('el presupuesto muestra estado con icono y palabra, y enlaza a los movimientos de la categoría', async () => {
    montar()
    const panel = await screen.findByRole('region', { name: 'Presupuesto vs. gasto real' })
    expect(within(panel).getAllByText(/Superado · /)).toHaveLength(2)
    expect(within(panel).getByText('Te pasaste $14.839')).toBeInTheDocument()
    const enlace = within(panel).getByRole('link', { name: /Comida: gastaste \$150\.000 de \$145\.161, Superado/ })
    expect(enlace).toHaveAttribute('href', '/movimientos?cat=Comida&tipo=expense&desde=2026-10-01&hasta=2026-10-15')
    expect(within(panel).getByText(/0,48 meses de límite/)).toBeInTheDocument()
  })

  it('sin movimientos en el periodo no dibuja gráficos vacíos: explica y ofrece otro periodo', async () => {
    const user = userEvent.setup()
    api.informeResumen = vi.fn().mockResolvedValue({ ...RESUMEN, hay_datos: false, etiqueta: 'octubre de 2026' })
    montar()
    expect(await screen.findByText('Aún no hay movimientos en octubre de 2026')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Flujo neto' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Ver 3 meses' }))
    await waitFor(() => expect(api.informeResumen).toHaveBeenLastCalledWith({ periodo: '3_meses' }))
  })

  it('un error de conexión se explica y se puede reintentar', async () => {
    const user = userEvent.setup()
    api.informeResumen = vi.fn().mockRejectedValueOnce(new Error('sin red')).mockResolvedValue(RESUMEN)
    montar()
    expect(await screen.findByRole('alert')).toHaveTextContent('sin red')
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('region', { name: '¿Me alcanzó la plata?' })).toBeInTheDocument()
  })

  it('los paneles se pueden ocultar y la elección se recuerda', async () => {
    const user = userEvent.setup()
    const { unmount } = montar()
    await screen.findByRole('region', { name: 'Flujo neto' })
    await user.click(screen.getByRole('button', { name: 'Personalizar paneles' }))
    await user.click(screen.getByRole('button', { name: 'Ocultar Flujo neto' }))
    expect(screen.queryByRole('region', { name: 'Flujo neto' })).toBeNull()
    unmount()
    montar()
    await screen.findByRole('region', { name: '¿Me alcanzó la plata?' })
    expect(screen.queryByRole('region', { name: 'Flujo neto' })).toBeNull()
  })
})

describe('Flujo neto: explorar y navegar al detalle', () => {
  it('con el teclado se elige un tramo y se ve su detalle con enlace a sus movimientos', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><FlujoNeto flujo={RESUMEN.flujo} fmt={fmt} agrupar="dia" onAgrupar={() => {}} /></MemoryRouter>)
    const grafico = screen.getByRole('group', { name: /Gráfico del flujo neto/ })
    grafico.focus()
    await user.keyboard('{ArrowRight}{Enter}')
    const detalle = await screen.findByTestId('flujo-detalle')
    expect(detalle).toHaveTextContent('1 de octubre')
    expect(detalle).toHaveTextContent('Entró $1.000.000 · salió $0 · flujo neto +$1.000.000')
    expect(within(detalle).getByRole('link', { name: /Ver los movimientos de este tramo/ })).toHaveAttribute('href', '/movimientos?desde=2026-10-01&hasta=2026-10-01')
  })

  it('el resumen en palabras da los totales y el mejor y el más ajustado', () => {
    render(<MemoryRouter><FlujoNeto flujo={RESUMEN.flujo} fmt={fmt} agrupar="dia" onAgrupar={() => {}} /></MemoryRouter>)
    expect(screen.getByText(/2 tramos con plata sobrante y 3 con plata faltante/)).toBeInTheDocument()
    expect(screen.getByText(/Tu mejor tramo: 1 de octubre \(\+\$1\.000\.000\)/)).toBeInTheDocument()
    expect(screen.getByText(/En total: \+\$1\.000\.000/)).toBeInTheDocument()
  })

  it('todos los tramos están en una tabla para lectores de pantalla, sin los tramos vacíos', () => {
    render(<MemoryRouter><FlujoNeto flujo={RESUMEN.flujo} fmt={fmt} agrupar="dia" onAgrupar={() => {}} /></MemoryRouter>)
    const tabla = screen.getByRole('table', { hidden: true })
    expect(within(tabla).getAllByRole('row', { hidden: true })).toHaveLength(1 + 5) // encabezado + 5 tramos con datos
  })

  it('sin datos dice que no hay, no dibuja un gráfico en cero', () => {
    render(<MemoryRouter><FlujoNeto flujo={{ ...RESUMEN.flujo, hay_datos: false, puntos: [punto(3, null, null)] }} fmt={fmt} agrupar="dia" onAgrupar={() => {}} /></MemoryRouter>)
    expect(screen.getByText(/No hay ingresos ni gastos en este periodo/)).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: /Gráfico del flujo neto/ })).toBeNull()
  })
})

describe('Tasa de ahorro', () => {
  it('muestra el promedio, deja el mes sin ingresos en blanco y permite abrir un mes', async () => {
    const user = userEvent.setup()
    const verMes = vi.fn()
    render(<MemoryRouter><TasaAhorro meses={RESUMEN.meses} resumen={RESUMEN.tasa_serie} fmt={fmt} onVerMes={verMes} /></MemoryRouter>)
    expect(screen.getByText('66,7 %')).toBeInTheDocument()
    expect(screen.getByText(/2 meses con ingresos/)).toBeInTheDocument()
    expect(screen.getByText(/Tu mejor mes: octubre de 2026 \(83,3 %\)\. El más bajo: septiembre de 2026 \(44,4 %\)/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /agosto de 2026, sin ingresos/ })).toBeInTheDocument()
    screen.getByRole('group', { name: /Gráfico de la tasa de ahorro/ }).focus()
    await user.keyboard('{ArrowRight}{ArrowRight}{Enter}')
    await user.click(await screen.findByRole('button', { name: /Ver septiembre de 2026 en todo el informe/ }))
    expect(verMes).toHaveBeenCalledWith('2026-09')
  })

  it('sin ingresos en ningún mes explica por qué no hay tasa', () => {
    const sin = RESUMEN.meses.map((m) => ({ ...m, ingresos: 0, tasa_ahorro: null }))
    render(<MemoryRouter><TasaAhorro meses={sin} resumen={{ promedio: null, mejor: null, peor: null, meses_con_tasa: 0 }} fmt={fmt} onVerMes={() => {}} /></MemoryRouter>)
    expect(screen.getByText(/necesitas ingresos registrados/)).toBeInTheDocument()
  })
})

describe('frases con la etiqueta del periodo', () => {
  it('no dice «en del…»', () => {
    expect(enPeriodo('octubre de 2026')).toBe('en octubre de 2026')
    expect(enPeriodo('del 1 de junio al 25 de noviembre de 2026')).toBe('en el periodo del 1 de junio al 25 de noviembre de 2026')
    expect(enPeriodo('los últimos 3 meses')).toBe('durante los últimos 3 meses')
  })
})

describe('Presupuesto sin presupuestos y cambios', () => {
  it('sin presupuestos invita a crear uno (no muestra barras vacías)', () => {
    render(<MemoryRouter><PresupuestoReal datos={{ hay_presupuestos: false, categorias: [] }} fmt={fmt} /></MemoryRouter>)
    expect(screen.getByRole('link', { name: 'Crear un presupuesto' })).toHaveAttribute('href', '/presupuesto')
  })

  it('un periodo recién empezado no muestra un «−100 %» engañoso y sin base lo dice', () => {
    const { container, rerender } = render(<Cambio pct={-100} actual={0} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<Cambio pct={null} actual={5} />)
    expect(screen.getByText('sin base para comparar')).toBeInTheDocument()
  })

  it('subir los gastos es malo (rojo) y subir los ingresos es bueno (verde), siempre con frase', () => {
    const { container, rerender } = render(<Cambio pct={20} actual={5} mejorSube={false} />)
    expect(container.firstChild.className).toContain('text-danger')
    rerender(<Cambio pct={20} actual={5} mejorSube />)
    expect(container.firstChild.className).toContain('text-cuadra')
    expect(screen.getByText('sube 20 % frente al periodo anterior')).toBeInTheDocument()
  })
})
