// «Lo que te cuesta tu plata»: piezas puras para la pantalla /costos, la tarjeta de Inicio y los enlaces.
// El análisis lo hace el servidor (backend/app/costos_bancarios.py); aquí solo se presenta.

// Tipos de cobro, con el color de la serie del tema (index.css: --c-serie-N). El color nunca es la única
// señal: cada barra lleva su nombre y su monto.
export const TIPOS_COSTO = [
  { clave: 'intereses', nombre: 'Intereses de tarjeta', color: 'var(--c-serie-1)', ayuda: 'intereses-de-mora' },
  { clave: 'cuota', nombre: 'Cuota de manejo', color: 'var(--c-serie-4)', ayuda: 'cuota-de-manejo' },
  { clave: 'comisiones', nombre: 'Comisiones y seguros', color: 'var(--c-serie-3)', ayuda: 'seguro-de-deudores' },
  { clave: 'gmf', nombre: '4x1000 (GMF)', color: 'var(--c-serie-5)', ayuda: '4x1000' },
]

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

export function nombreMes(clave) {
  const [anio, mes] = String(clave || '').split('-')
  return MESES[Number(mes) - 1] ? `${MESES[Number(mes) - 1]} de ${anio}` : ''
}

export function mesCorto(clave) {
  const [, mes] = String(clave || '').split('-')
  return MESES[Number(mes) - 1]?.slice(0, 3) || ''
}

// ¿Vale la pena mostrar algo? Respuestas vacías, listas ([]) o sin cobros ni rendimientos no muestran nada.
export function hayCostos(d) {
  if (!d || Array.isArray(d) || !d.tiene_datos) return false
  return (d.anio?.total || 0) > 0 || (d.anio?.rendimientos || 0) > 0 || (d.mes?.total || 0) > 0
}

// Frase de comparación con el mes anterior, en lenguaje llano.
export function textoVariacion(mes) {
  if (!mes || mes.variacion_pct == null) return 'Aún no hay un mes anterior con qué comparar.'
  if (mes.variacion_pct === 0) return 'Igual que el mes pasado.'
  const sube = mes.variacion_pct > 0
  return `${sube ? 'Subió' : 'Bajó'} ${Math.abs(mes.variacion_pct)} % frente al mes pasado.`
}

// Barras por tipo: porcentaje de la más grande (para que se vea la proporción) y de qué tipo pesa más.
export function barrasPorTipo(bloque) {
  const filas = TIPOS_COSTO.map((t) => ({ ...t, monto: bloque?.[t.clave] || 0 }))
  const max = Math.max(1, ...filas.map((f) => f.monto))
  return filas.map((f) => ({ ...f, pct: Math.round((f.monto / max) * 100) }))
}
