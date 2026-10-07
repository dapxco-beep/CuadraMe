import { COLORES, GraficoBarras } from './graficos'

const MESES_CORTOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

function etiquetaMes(clave) {
  const [, mes] = clave.split('-')
  return MESES_CORTOS[parseInt(mes, 10) - 1]
}

const SERIES = [
  { nombre: 'Ingresos', color: COLORES.ingreso },
  { nombre: 'Gastos', color: COLORES.gasto },
]

// Delega en el sistema único de gráficas (components/graficos).
export default function GraficoTendencia({ meses }) {
  const datos = meses.map((m) => ({ clave: m.mes, etiqueta: etiquetaMes(m.mes), valores: [m.ingresos, m.gastos] }))
  return <GraficoBarras datos={datos} series={SERIES} titulo="Ingresos y gastos de los últimos meses" />
}
