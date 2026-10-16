// Nombre propio de un movimiento. El texto del banco (`descripcion`) nunca se pierde:
// el servidor sigue usándolo para duplicados, reglas y cuadre. Aquí solo se decide qué se MUESTRA.

export const MAX_NOMBRE = 80
// Desde cuántas veces repetido el comercio se sugiere «Recordar este nombre» (igual que el servidor).
export const MIN_REPETICIONES_NOMBRE = 4

/** Lo que se ve primero: el nombre que puso la persona o, si no hay, el texto del banco. */
export const nombreDe = (m) => (m?.titulo && String(m.titulo).trim()) || m?.descripcion || ''

/** ¿Hay nombre propio distinto del texto del banco? (entonces se muestra «Banco: …» en pequeño) */
export const tieneNombrePropio = (m) => Boolean(m?.titulo && String(m.titulo).trim() && m.titulo.trim() !== (m.descripcion || '').trim())

/** Limpia lo que escribe la persona: sin etiquetas, sin espacios repetidos, máximo 80. */
export function limpiarNombre(texto) {
  return String(texto ?? '')
    .replace(/<[^>]*>/g, '')
    .replace(/[<>]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, MAX_NOMBRE)
    .trim()
}
