import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import ResumenCifras from '../components/informe/ResumenCifras'
import FlujoNeto from '../components/informe/FlujoNeto'
import TasaAhorro from '../components/informe/TasaAhorro'
import IngresosFuente from '../components/informe/IngresosFuente'
import PresupuestoReal from '../components/informe/PresupuestoReal'
import Hallazgos from '../components/informe/Hallazgos'
import HeroGasto from '../components/informe/HeroGasto'

const fmt = (v) => `$${Math.abs(Math.round(v)).toLocaleString('es-CO')}`
const dentro = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>)
// Ningún panel puede mostrar valores rotos, sea cual sea el dato que falte.
const sinValoresRotos = (container) => expect(container.textContent).not.toMatch(/NaN|undefined|Infinity|null/)

const ANT_VACIO = { desde: '2026-08-01', hasta: '2026-08-31', etiqueta: 'agosto de 2026', ingresos: 0, gastos: 0, balance: 0, tasa_ahorro: null }
const BASE = {
  etiqueta: 'septiembre de 2026', ingresos: 1_000_000, gastos: 400_000, balance: 600_000, tasa_ahorro: 60, en_curso: false,
  anterior: ANT_VACIO, variacion: { ingresos_pct: null, gastos_pct: null, balance_pct: null, tasa_ahorro_puntos: null },
}

describe('Resumen de cifras con datos que faltan', () => {
  it('sin periodo anterior explica UNA vez que no hay con qué comparar (no repite «sin base» en cada cifra)', () => {
    const { container } = dentro(<ResumenCifras d={BASE} fmt={fmt} />)
    expect(screen.getByTestId('sin-base')).toHaveTextContent('No hay movimientos en agosto de 2026')
    expect(screen.queryAllByText('sin base para comparar')).toHaveLength(0)
    expect(screen.queryByText(/sigue en curso/)).toBeNull()                // tampoco finge una comparación «justa»
    sinValoresRotos(container)
  })

  it('con periodo anterior sí compara, y una cifra sin base propia lo dice solo en esa cifra', () => {
    const d = { ...BASE, anterior: { ...ANT_VACIO, ingresos: 0, gastos: 100_000, balance: -100_000 }, variacion: { ingresos_pct: null, gastos_pct: 300, balance_pct: null, tasa_ahorro_puntos: null } }
    dentro(<ResumenCifras d={d} fmt={fmt} />)
    expect(screen.queryByTestId('sin-base')).toBeNull()
    expect(screen.getByText('sube 300 % frente al periodo anterior')).toBeInTheDocument()
    expect(screen.getAllByText('sin base para comparar').length).toBeGreaterThanOrEqual(1)
  })

  it('sin ingresos no hay tasa de ahorro: se ve «—» y «sin ingresos», nunca 0 %', () => {
    const d = { ...BASE, ingresos: 0, balance: -400_000, tasa_ahorro: null }
    const { container } = dentro(<ResumenCifras d={d} fmt={fmt} />)
    expect(screen.getByLabelText(/Flujo neto: te faltó \$400\.000/)).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText('sin ingresos')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/0 %/)
    sinValoresRotos(container)
  })

  it('flujo neto en cero se dice en palabras', () => {
    dentro(<ResumenCifras d={{ ...BASE, ingresos: 100, gastos: 100, balance: 0, tasa_ahorro: 0 }} fmt={fmt} />)
    expect(screen.getByLabelText('Flujo neto: quedaste en cero')).toBeInTheDocument()
  })
})

describe('Gráficos con datos que faltan', () => {
  const punto = (dia, ing, gas) => ({
    clave: `2026-09-${String(dia).padStart(2, '0')}`, etiqueta: String(dia), etiqueta_larga: `${dia} de septiembre`,
    desde: `2026-09-${String(dia).padStart(2, '0')}`, hasta: `2026-09-${String(dia).padStart(2, '0')}`,
    ingresos: ing, gastos: gas, neto: ing === null ? null : ing - gas, acumulado: ing === null ? 0 : ing - gas, con_datos: ing !== null,
  })

  it('flujo con un solo tramo no rompe ni inventa «mejor/peor» distintos', () => {
    const flujo = { agrupar: 'dia', puntos: [punto(1, 500_000, 100_000)], positivos: 1, negativos: 0, mejor: '2026-09-01', peor: '2026-09-01', hay_datos: true }
    const { container } = dentro(<FlujoNeto flujo={flujo} fmt={fmt} agrupar="dia" onAgrupar={() => {}} />)
    expect(screen.getByText(/1 tramo con plata sobrante y 0 con plata faltante/)).toBeInTheDocument()
    expect(screen.queryByText(/El más ajustado/)).toBeNull()
    sinValoresRotos(container)
  })

  it('flujo con todos los tramos vacíos no dibuja nada y lo explica', () => {
    const flujo = { agrupar: 'semana', puntos: [punto(1, null, null), punto(8, null, null)], positivos: 0, negativos: 0, mejor: null, peor: null, hay_datos: false }
    const { container } = dentro(<FlujoNeto flujo={flujo} fmt={fmt} agrupar="semana" onAgrupar={() => {}} />)
    expect(screen.getByText(/No hay ingresos ni gastos en este periodo/)).toBeInTheDocument()
    expect(container.querySelector('[aria-roledescription="gráfico interactivo"]')).toBeNull()
    sinValoresRotos(container)
  })

  it('flujo solo con pérdidas: no dice «mejor tramo» positivo', () => {
    const flujo = { agrupar: 'dia', puntos: [punto(1, 0, 100_000), { ...punto(2, 0, 50_000), acumulado: -150_000 }], positivos: 0, negativos: 2, mejor: '2026-09-02', peor: '2026-09-01', hay_datos: true }
    dentro(<FlujoNeto flujo={flujo} fmt={fmt} agrupar="dia" onAgrupar={() => {}} />)
    expect(screen.getByText(/0 tramos con plata sobrante y 2 con plata faltante/)).toBeInTheDocument()
    expect(screen.getByText(/En total: −\$150\.000/)).toBeInTheDocument()
  })

  it('tasa de ahorro con un solo mes muestra el punto sin línea ni tendencia inventada', () => {
    const meses = [{ mes: '2026-09', etiqueta: 'Sep', etiqueta_larga: 'septiembre de 2026', ingresos: 1_000_000, gastos: 400_000, balance: 600_000, tasa_ahorro: 60 }]
    const resumen = { promedio: 60, meses_con_tasa: 1, mejor: { mes: '2026-09', etiqueta_larga: 'septiembre de 2026', tasa_ahorro: 60 }, peor: { mes: '2026-09', etiqueta_larga: 'septiembre de 2026', tasa_ahorro: 60 } }
    const { container } = dentro(<TasaAhorro meses={meses} resumen={resumen} fmt={fmt} onVerMes={() => {}} />)
    expect(container.querySelector('path.gr-linea')).toBeNull()
    expect(screen.queryByText(/El más bajo/)).toBeNull()
    expect(screen.getByText(/1 mes con ingresos/)).toBeInTheDocument()
    sinValoresRotos(container)
  })

  it('tasa de ahorro muy negativa se grafica acotada pero el valor real se lee', () => {
    const meses = [
      { mes: '2026-08', etiqueta: 'Ago', etiqueta_larga: 'agosto de 2026', ingresos: 100_000, gastos: 900_000, balance: -800_000, tasa_ahorro: -800 },
      { mes: '2026-09', etiqueta: 'Sep', etiqueta_larga: 'septiembre de 2026', ingresos: 1_000_000, gastos: 500_000, balance: 500_000, tasa_ahorro: 50 },
    ]
    const resumen = { promedio: -27.3, meses_con_tasa: 2, mejor: { mes: '2026-09', etiqueta_larga: 'septiembre de 2026', tasa_ahorro: 50 }, peor: { mes: '2026-08', etiqueta_larga: 'agosto de 2026', tasa_ahorro: -800 } }
    const { container } = dentro(<TasaAhorro meses={meses} resumen={resumen} fmt={fmt} onVerMes={() => {}} />)
    expect(screen.getByRole('img', { name: /agosto de 2026, -800 %/ })).toBeInTheDocument()   // el valor real, no el recortado
    expect(screen.getByText(/El más bajo: agosto de 2026 \(-800 %\)/)).toBeInTheDocument()
    sinValoresRotos(container)
  })

  it('ingresos por fuente sin datos y con «otras fuentes»', () => {
    const { container, rerender } = dentro(<IngresosFuente datos={{ total: 0, fuentes: [], otras: null, hay_datos: false }} fmt={fmt} paramsPeriodo={{ periodo: 'este_mes' }} />)
    expect(screen.getByText('No registraste ingresos en este periodo.')).toBeInTheDocument()
    rerender(<MemoryRouter><IngresosFuente datos={{ total: 300_000, hay_datos: true, fuentes: [{ clave: 'a', nombre: 'A', categoria: 'X', monto: 200_000, pct: 66.7, num: 1, anterior: 0, variacion_pct: null }], otras: { cantidad: 2, monto: 100_000, pct: 33.3, num: 3 } }} fmt={fmt} paramsPeriodo={{ periodo: 'este_mes' }} /></MemoryRouter>)
    expect(screen.getByText('Otras fuentes (2)')).toBeInTheDocument()
    expect(screen.getByText(/3 movimientos/)).toBeInTheDocument()
    sinValoresRotos(container)
  })

  it('presupuesto con un límite en cero no muestra NaN ni porcentajes inventados', () => {
    const datos = {
      hay_presupuestos: true, presupuesto_total: 0, gastado_total: 50_000, disponible_total: -50_000, pct_total: null, gasto_sin_presupuesto: 0, meses_equivalentes: 1,
      categorias: [{ categoria: 'Ocio', presupuesto: 0, gastado: 50_000, disponible: -50_000, pct: null, estado: 'sin_limite', alerta_pct: 80 }],
    }
    const { container } = dentro(<PresupuestoReal datos={datos} fmt={fmt} />)
    expect(screen.getByText(/Sin límite · —/)).toBeInTheDocument()
    sinValoresRotos(container)
  })
})

describe('Hallazgos sin nada que afirmar', () => {
  it('lista vacía: no pinta el panel (no rellena con consejos genéricos)', () => {
    const { container } = dentro(<Hallazgos hallazgos={[]} etiqueta="septiembre de 2026" />)
    expect(container).toBeEmptyDOMElement()
  })
  it('un hallazgo muestra su título, sus cifras y el detalle', () => {
    dentro(<Hallazgos etiqueta="septiembre de 2026" hallazgos={[{ id: 'x', tono: 'atento', titulo: 'No registraste ingresos en este periodo', texto: 'Salió $400.000 en septiembre de 2026.', enlace: '/agregar?tipo=ingreso' }]} />)
    const panel = screen.getByRole('region', { name: 'Lo que dicen tus números' })
    expect(within(panel).getByText('Salió $400.000 en septiembre de 2026.')).toBeInTheDocument()
    expect(within(panel).getByRole('link', { name: 'Ver el detalle' })).toHaveAttribute('href', '/agregar?tipo=ingreso')
  })
})

describe('Gastos: resumen del periodo con datos que faltan', () => {
  const informe = (extra = {}) => ({
    etiqueta: 'del 1 de junio de 2026 al 26 de noviembre de 2026', total: 18_779_200, ingresos: 20_518_000, ahorro: 1_738_800,
    total_anterior: 0, variacion_pct: null, anterior: { etiqueta: 'los 179 días anteriores (4 dic - 31 may)' }, ...extra,
  })
  it('un periodo anterior vacío se explica una vez (sin barra «Antes» ni «sin base» suelto) y la frase se lee bien', () => {
    const { container } = dentro(<HeroGasto informe={informe()} fmt={fmt} esMesActual={false} />)
    expect(screen.getByText(/Gastaste en el periodo del 1 de junio de 2026 al 26 de noviembre de 2026/)).toBeInTheDocument()
    expect(screen.getByText(/No hubo gastos durante los 179 días anteriores \(4 dic - 31 may\), así que todavía no hay con qué comparar/)).toBeInTheDocument()
    expect(screen.queryByText('Antes')).toBeNull()
    expect(screen.queryByText('sin base para comparar')).toBeNull()
    sinValoresRotos(container)
  })
  it('con periodo anterior sí compara y muestra la barra «Antes»', () => {
    dentro(<HeroGasto informe={informe({ total_anterior: 10_000_000, variacion_pct: 87.8, etiqueta: 'octubre de 2026', anterior: { etiqueta: 'septiembre de 2026' } })} fmt={fmt} esMesActual={false} />)
    expect(screen.getByText(/Gastaste en octubre de 2026/)).toBeInTheDocument()
    expect(screen.getByText(/frente a septiembre de 2026/)).toBeInTheDocument()
    expect(screen.getByText('Antes')).toBeInTheDocument()
  })
})
