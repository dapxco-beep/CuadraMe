// «Arreglar mis extractos de la tarjeta»: textos y reglas puras (sin React) para probarlas fácil.
// Los textos siguen docs/GUIA_DE_TEXTOS.md: la plata de la persona, sin jerga, sin emojis.
import { nombreMes } from './sincronizacion'

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`
const capital = (t) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : '')

export const textoBoton = (n) => `Arreglar mis extractos de la tarjeta (${n})`

export const mesDe = (e) => capital(nombreMes(e?.mes)) || 'Extracto'

/** Qué se hará con un extracto: «Julio 2026 · pasa de Nu Colombia a Nu Colombia Crédito · 2 movimientos». */
export function lineaExtracto(e) {
  const partes = [mesDe(e)]
  if (e.cuenta_destino) {
    partes.push(`pasa de ${e.cuenta_actual.nombre} a ${e.cuenta_destino.nombre}`)
    if (e.movera) partes.push(plural(e.movera, 'movimiento', 'movimientos'))
  } else if (e.releera) {
    partes.push('lo leo otra vez con el lector de hoy')
  }
  return partes.join(' · ')
}

/** Aviso corto cuando un extracto puede no leerse (clave del PDF o Gmail). '' si no hay nada que avisar. */
export function avisoExtracto(e) {
  if (!e.releera) return ''
  if (!e.puede_releerse) return 'Conecta Gmail para releerlo.'
  if (e.requiere_clave) return 'Necesita la clave de tu PDF; si no abre, lo dejo para después.'
  return ''
}

/** «Nu Colombia: de $880.000 a $1.000.000». */
export function textoSaldo(c, fmt) {
  return `${c.nombre}: de ${fmt(c.saldo_antes)} a ${fmt(c.saldo_despues)}`
}

export const textoProgreso = (i, n) => `Arreglando ${i} de ${n}…`

/** «Arreglé 6 extractos: moví 36 movimientos a tu tarjeta, encontré 41 compras por importar.» */
export function resumenFinal({ arreglados = 0, movidos = 0, por_importar: nuevas = 0, saltados = 0, restantes = 0 }) {
  if (!arreglados && !saltados) return 'Tus extractos de la tarjeta ya estaban bien. No cambié nada.'
  const partes = []
  if (movidos) partes.push(`moví ${plural(movidos, 'movimiento', 'movimientos')} a tu tarjeta`)
  if (nuevas) partes.push(`encontré ${plural(nuevas, 'compra', 'compras')} por importar`)
  if (!partes.length) partes.push('no encontré nada nuevo por importar')
  let frase = arreglados ? `Arreglé ${plural(arreglados, 'extracto', 'extractos')}: ${partes.join(', ')}` : 'No pude arreglar nada ahora'
  if (saltados) frase += `. ${plural(saltados, 'extracto quedó', 'extractos quedaron')} para después`
  if (restantes) frase += `. Quedan ${restantes} por arreglar: toca el botón otra vez`
  return `${frase}.`
}

/** Junta lo que devolvió cada paso (la app arregla de a uno para mostrar el avance). */
export function juntarResultados(pasos, restantes = 0) {
  const resultados = pasos.flatMap((p) => p.resultados || [])
  const hecho = (r) => r.estado === 'arreglado' || r.estado === 'parcial'
  const t = {
    arreglados: resultados.filter(hecho).length,
    saltados: resultados.filter((r) => r.estado === 'saltado' || r.estado === 'parcial').length,
    movidos: resultados.reduce((s, r) => s + (r.movidos || 0), 0),
    por_importar: resultados.reduce((s, r) => s + (r.nuevas || 0), 0),
    restantes,
    resultados,
  }
  return { ...t, resumen: resumenFinal(t) }
}

/** Una línea por extracto en el resultado final. */
export function lineaResultado(r) {
  const mes = mesDe(r)
  if (r.estado === 'saltado') return `${mes}: para después. ${r.motivo || ''}`.trim()
  const partes = []
  if (r.mensaje_lectura) partes.push(r.mensaje_lectura)
  if (r.movidos) partes.push(`Moví ${plural(r.movidos, 'movimiento', 'movimientos')}`)
  if (r.nuevas) partes.push(`${plural(r.nuevas, 'compra nueva', 'compras nuevas')} por importar`)
  if (r.estado === 'parcial') partes.push(`Para después: ${r.motivo || 'la lectura'}`)
  return `${mes}: ${partes.join(' · ') || 'sin cambios'}`
}
