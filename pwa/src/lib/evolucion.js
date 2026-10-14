// Utilidades puras de la gráfica evolutiva (sin React): lectura automática en tono Cuadri,
// resumen para lectores de pantalla y separación en tramos (los meses sin datos son hueco,
// nunca un cero engañoso). Se prueban en src/test/evolucion.test.jsx.

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

// '2026-08' -> 'agosto'; una semana ('2026-10-12') devuelve su etiqueta larga.
export function nombreCorto(p, agrupar) {
  if (agrupar === 'semana') return p.etiqueta_larga
  const m = parseInt(String(p.clave).split('-')[1], 10)
  return MESES[m - 1]
}

// Tramos continuos de puntos con datos: un hueco corta la línea.
export function tramos(puntos, clave) {
  const out = []
  let actual = []
  puntos.forEach((p, i) => {
    if (p.con_datos && p[clave] !== null && p[clave] !== undefined) actual.push({ i, p })
    else if (actual.length) {
      out.push(actual)
      actual = []
    }
  })
  if (actual.length) out.push(actual)
  return out
}

function pct(a, b) {
  return b ? Math.round(((a - b) / Math.abs(b)) * 100) : null
}

// Frases de lectura (máx. 3). Sin culpar: describen, no juzgan.
export function lecturaEvolucion(puntos, agrupar, fmt) {
  const con = puntos.filter((p) => p.con_datos)
  if (con.length < 2) return []
  const unidad = agrupar === 'semana' ? 'semana' : 'mes'
  const cerrados = con.filter((p) => !p.en_curso)
  const frases = []

  const mejor = cerrados.reduce((m, p) => (m === null || p.ahorro > m.ahorro ? p : m), null)
  if (mejor) {
    if (mejor.ahorro > 0) {
      frases.push(
        agrupar === 'semana'
          ? `Tu mejor ${unidad} para ahorrar fue la ${mejor.etiqueta_larga}: ${fmt(mejor.ahorro)}.`
          : `Tu ahorro fue mayor en ${nombreCorto(mejor, agrupar)}: ${fmt(mejor.ahorro)}.`,
      )
    } else {
      frases.push(
        `En ${agrupar === 'semana' ? 'estas semanas' : 'estos meses'} lo que salió fue parecido o mayor a lo que entró. Pasa; en «En qué gasto mi plata» puedes ver adónde se fue.`,
      )
    }
  }

  // Compara los dos últimos periodos cerrados que sean seguidos en la serie.
  if (cerrados.length >= 2) {
    const b = cerrados[cerrados.length - 1]
    const a = cerrados[cerrados.length - 2]
    const cambio = pct(b.gastos, a.gastos)
    const seguidos = puntos.indexOf(b) - puntos.indexOf(a) === 1
    if (seguidos && cambio !== null && Math.abs(cambio) >= 5) {
      const sujeto = agrupar === 'semana' ? 'la última semana completa' : nombreCorto(b, agrupar)
      const previo = agrupar === 'semana' ? 'la anterior' : nombreCorto(a, agrupar)
      frases.push(
        cambio > 0
          ? `En ${sujeto} gastaste ${cambio} % más que en ${previo}.`
          : `En ${sujeto} gastaste ${Math.abs(cambio)} % menos que en ${previo}. Buen ritmo.`,
      )
    }
  }

  const enCurso = con.find((p) => p.en_curso)
  if (enCurso) {
    frases.push(
      agrupar === 'semana'
        ? 'La semana en curso aún no termina: sus números pueden cambiar.'
        : `${nombreCorto(enCurso, agrupar)[0].toUpperCase()}${nombreCorto(enCurso, agrupar).slice(1)} sigue en curso: sus números pueden cambiar.`,
    )
  }
  return frases
}

export function resumenAria(puntos, agrupar, fmt) {
  const con = puntos.filter((p) => p.con_datos)
  const por = agrupar === 'semana' ? 'semana' : 'mes'
  return (
    `Evolución de ingresos, gastos y ahorro por ${por}. ` +
    puntos
      .map((p) =>
        p.con_datos
          ? `${p.etiqueta_larga}${p.en_curso ? ' (en curso)' : ''}: ingresos ${fmt(p.ingresos)}, gastos ${fmt(p.gastos)}, ahorro ${fmt(p.ahorro)}`
          : `${p.etiqueta_larga}: sin movimientos`,
      )
      .join('; ') +
    (con.length ? '' : '.')
  )
}

// Separa etiquetas que se pisarían al final de las líneas (mínimo `sep` px entre una y otra).
export function repartirEtiquetas(items, sep = 11) {
  const orden = [...items].sort((a, b) => a.y - b.y)
  for (let i = 1; i < orden.length; i++) {
    if (orden[i].y - orden[i - 1].y < sep) orden[i] = { ...orden[i], y: orden[i - 1].y + sep }
  }
  return orden
}

