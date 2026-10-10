// Estado de categorización de cada línea de una revisión (extracto o archivo) y su resumen.
// Sin React: reglas puras, fáciles de probar.
//
//   confirmada    la persona eligió la categoría en esta revisión
//   auto          la app la puso sola con seguridad (regla tuya, aprendida o comercio conocido)
//   revisar       la app tiene una sugerencia pero no está segura: conviene mirarla
//   sin_categoria no hay sugerencia («Otros»)

// Emoji de respaldo: categoria sin icono propio y linea sin categoria (como escapes, porque el
// emoji de cada categoria es un dato de la persona).
export const EMOJI_DEFECTO = '\u{1F4B3}'
export const EMOJI_SIN_CATEGORIA = '\u2754'

export const UMBRAL_AUTO = 0.75 // igual que CONFIANZA_AUTOIMPORT_DEFAULT del servidor

export const ESTADOS_CATEGORIA = {
  confirmada: { texto: 'Elegida por ti', corto: 'Elegida', clase: 'bg-cuadra-soft text-cuadra' },
  auto: { texto: 'Categorizado automáticamente', corto: 'Automático', clase: 'bg-cuadra-soft text-cuadra' },
  revisar: { texto: 'Necesita tu revisión', corto: 'Por revisar', clase: 'bg-accent-soft text-accent' },
  sin_categoria: { texto: 'Sin categoría', corto: 'Sin categoría', clase: 'bg-danger-soft text-danger' },
}

/**
 * `item`: { categoria (la sugerida), razon, confianza }.
 * `elegida`: la categoría que quedó en la revisión (puede ser la que cambió la persona).
 */
export function estadoCategoria(item, elegida) {
  const actual = elegida || item?.categoria || 'Otros'
  const sugerida = item?.categoria || 'Otros'
  if (actual !== sugerida && actual !== 'Otros') return 'confirmada'
  if (!actual || actual === 'Otros') return 'sin_categoria'
  const segura = item?.confianza == null ? Boolean(item?.razon) : item.confianza >= UMBRAL_AUTO
  return segura ? 'auto' : 'revisar'
}

/** Cuenta los estados de una lista de líneas ya resueltas: [{ estado }]. */
export function resumirCategorias(estados) {
  const r = { auto: 0, confirmada: 0, revisar: 0, sin_categoria: 0 }
  for (const e of estados) if (e in r) r[e] += 1
  return { ...r, categorizados: r.auto + r.confirmada, total: r.auto + r.confirmada + r.revisar + r.sin_categoria }
}

/** «37 categorizados, 5 por revisar» (y «2 sin categoría» si hay). */
export function textoResumenCategorias(r) {
  const partes = [
    r.categorizados === 1 ? '1 categorizado' : `${r.categorizados} categorizados`,
    `${r.revisar} por revisar`,
  ]
  if (r.sin_categoria) partes.push(`${r.sin_categoria} sin categoría`)
  return partes.join(', ')
}

