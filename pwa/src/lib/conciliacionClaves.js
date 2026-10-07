// Dos movimientos idénticos el mismo día (dos compras de $5.000 en la misma tienda) comparten
// huella (fingerprint). Para React cada fila necesita una clave única y estable: huella + el
// número de aparición (#0, #1...).
export function clavesFilas(items) {
  const vistas = new Map()
  return items.map((m) => {
    const n = vistas.get(m.fingerprint) || 0
    vistas.set(m.fingerprint, n + 1)
    return `${m.fingerprint}#${n}`
  })
}

// Cuántas filas del extracto se importarán: el servidor importa por huella (todas las filas
// "faltantes" con esa huella), así que se cuentan filas, no huellas.
export function filasAImportar(review, seleccionados) {
  return review.filter((m) => m.estado === 'faltante' && seleccionados.has(m.fingerprint)).length
}

// Cuántas filas "faltantes" comparten huella con ésta (las gemelas se marcan juntas).
export function gemelasFaltantes(review, fingerprint) {
  return review.filter((m) => m.estado === 'faltante' && m.fingerprint === fingerprint).length
}
