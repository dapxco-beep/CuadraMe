// «Registrar los rendimientos de mis extractos»: textos y reglas puras (sin React) para probarlas fácil.
// Los textos siguen docs/GUIA_DE_TEXTOS.md: la plata de la persona, sin jerga, sin emojis.
import { nombreMes } from './sincronizacion'

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`
const capital = (t) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : '')

export const textoBoton = (n) => `Registrar los rendimientos de mis extractos (${n})`

export const mesDe = (e) => capital(nombreMes(e?.mes)) || 'Extracto'

/** «Septiembre 2026 · Nu Colombia · unos $9.000». «unos» cuando el monto es un cálculo y no se ha leído el PDF. */
export function lineaExtracto(e, fmt) {
  return [mesDe(e), e.cuenta?.nombre, `${e.estimado ? 'unos ' : ''}${fmt(e.monto)}`].filter(Boolean).join(' · ')
}

/** Cuánto suman, antes de confirmar. */
export function textoTotal(previa, fmt) {
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

export const textoProgreso = (i, n) => `Registrando ${i} de ${n}…`

/** «Registré los rendimientos de 8 extractos: $123.456 en total.» */
export function resumenFinal({ registrados = 0, total = 0, saltados = 0, restantes = 0 }, fmt) {
  if (!registrados && !saltados) return 'Tus extractos ya tienen sus rendimientos. No cambié nada.'
  let frase = registrados
    ? `Registré los rendimientos de ${plural(registrados, 'extracto', 'extractos')}: ${fmt(total)} en total`
    : 'No pude registrar ningún rendimiento ahora'
  if (saltados) frase += `. ${plural(saltados, 'extracto quedó', 'extractos quedaron')} para después`
  if (restantes) frase += `. Quedan ${restantes} por registrar: toca el botón otra vez`
  return `${frase}.`
}

/** Junta lo que devolvió cada paso (la app registra de a uno para mostrar el avance). */
export function juntarResultados(pasos, restantes = 0, fmt) {
  const resultados = pasos.flatMap((p) => p.resultados || [])
  const t = {
    registrados: resultados.filter((r) => r.estado === 'registrado').length,
    saltados: resultados.filter((r) => r.estado === 'saltado').length,
    total: resultados.reduce((s, r) => s + (r.monto || 0), 0),
    restantes,
    resultados,
  }
  return { ...t, resumen: resumenFinal(t, fmt) }
}

/** Una línea por extracto en el resultado final. */
export function lineaResultado(r, fmt) {
  const mes = mesDe(r)
  if (r.estado === 'saltado') return `${mes}: para después. ${r.motivo || ''}`.trim()
  if (r.estado === 'registrado') return `${mes}: ${fmt(r.monto)} de rendimientos registrados`
  return `${mes}: ${r.motivo || 'sin cambios'}`
}
