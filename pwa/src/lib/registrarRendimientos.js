// «Completar mis extractos: rendimientos e impuestos»: textos y reglas puras (sin React) para probarlas fácil.
// El resumen de un extracto de ahorros trae rendimientos (ingreso), impuesto del 4x1000 y costos por retiro (gastos) que no
// son líneas de movimientos. Los textos siguen docs/GUIA_DE_TEXTOS.md: la plata de la persona, sin jerga, sin emojis.
import { nombreMes } from './sincronizacion'

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`
const capital = (t) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : '')

/** Los conceptos del resumen, en el orden en que se cuentan. */
export const CONCEPTOS = [
  ['rendimientos', 'rendimientos'],
  ['impuesto_4x1000', '4x1000'],
  ['costos_retiro', 'costos por retiro'],
]

/** «$9.000 de rendimientos, $4.000 de 4x1000 y $6.500 de costos por retiro» ('' si no hay ninguno). */
export function frasePorConcepto(conceptos, fmt) {
  const partes = CONCEPTOS.filter(([k]) => (conceptos?.[k] || 0) > 0).map(([k, nombre]) => `${fmt(conceptos[k])} de ${nombre}`)
  if (partes.length <= 1) return partes[0] || ''
  return `${partes.slice(0, -1).join(', ')} y ${partes[partes.length - 1]}`
}

export const textoBoton = (n) => `Completar mis extractos: rendimientos e impuestos (${n})`

export const mesDe = (e) => capital(nombreMes(e?.mes)) || 'Extracto'

/** «Septiembre 2026 · Nu Colombia · unos $9.000». «unos» cuando el monto es un cálculo y no se ha leído el PDF. */
export function lineaExtracto(e, fmt) {
  const exacto = !e.estimado && frasePorConcepto(e.conceptos, fmt)
  return [mesDe(e), e.cuenta?.nombre, exacto || `${e.estimado ? 'unos ' : ''}${fmt(e.monto)}`].filter(Boolean).join(' · ')
}

/** Cuánto suman, antes de confirmar: por concepto lo ya leído, y aparte lo que falta por leer. */
export function textoTotal(previa, fmt) {
  const exacto = frasePorConcepto(previa?.por_concepto, fmt)
  const porLeer = previa?.por_determinar || 0
  if (exacto) {
    return porLeer > 0
      ? `En total, ${exacto}. Además, unos ${fmt(porLeer)} que salen de leer cada extracto otra vez.`
      : `En total, ${exacto}.`
  }
  const total = fmt(previa?.total_pesos || 0)
  return previa?.aproximado
    ? `En total, unos ${total}. El valor exacto sale de leer cada extracto otra vez.`
    : `En total, ${total}.`
}

/** Aviso corto cuando un extracto puede no leerse (clave del PDF o Gmail). '' si no hay nada que avisar. */
export function avisoExtracto(e) {
  if (!e.releera) return ''
  if (!e.puede_releerse) return 'Conecta Gmail para leerlo.'
  if (e.requiere_clave) return 'Necesita la clave de tu PDF; si no abre, lo dejo para después.'
  return ''
}

export const textoProgreso = (i, n) => `Completando ${i} de ${n}…`

/** «Completé 8 extractos: $123.456 de rendimientos y $34.000 de 4x1000.» */
export function resumenFinal({ registrados = 0, porConcepto = {}, total = 0, saltados = 0, restantes = 0 }, fmt) {
  if (!registrados && !saltados) return 'Tus extractos ya están completos. No cambié nada.'
  const detalle = frasePorConcepto(porConcepto, fmt) || fmt(total)
  let frase = registrados
    ? `Completé ${plural(registrados, 'extracto', 'extractos')}: ${detalle}`
    : 'No pude completar ningún extracto ahora'
  if (saltados) frase += `. ${plural(saltados, 'extracto quedó', 'extractos quedaron')} para después`
  if (restantes) frase += `. Quedan ${restantes} por completar: toca el botón otra vez`
  return `${frase}.`
}

/** Junta lo que devolvió cada paso (la app completa de a uno para mostrar el avance). */
export function juntarResultados(pasos, restantes = 0, fmt) {
  const resultados = pasos.flatMap((p) => p.resultados || [])
  const porConcepto = {}
  for (const r of resultados) {
    const c = r.conceptos || (r.estado === 'registrado' && r.monto ? { rendimientos: r.monto } : {})
    for (const [k, v] of Object.entries(c)) porConcepto[k] = (porConcepto[k] || 0) + v
  }
  const t = {
    registrados: resultados.filter((r) => r.estado === 'registrado').length,
    saltados: resultados.filter((r) => r.estado === 'saltado').length,
    total: resultados.reduce((s, r) => s + (r.monto || 0), 0),
    porConcepto,
    restantes,
    resultados,
  }
  return { ...t, resumen: resumenFinal(t, fmt) }
}

/** Una línea por extracto en el resultado final. */
export function lineaResultado(r, fmt) {
  const mes = mesDe(r)
  if (r.estado === 'saltado') return `${mes}: para después. ${r.motivo || ''}`.trim()
  if (r.estado === 'registrado') {
    const detalle = frasePorConcepto(r.conceptos, fmt) || `${fmt(r.monto)} de rendimientos`
    return `${mes}: ${detalle} registrados${r.motivo ? `. ${r.motivo}` : ''}`
  }
  return `${mes}: ${r.motivo || 'sin cambios'}`
}
