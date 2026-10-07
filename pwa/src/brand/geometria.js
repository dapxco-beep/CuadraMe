// Identidad CuadraMe — fuente ÚNICA de la geometría del isotipo.
// La usan la app (React), el script de íconos (Node) y el canvas del Wrapped,
// así el logo nunca se desincroniza entre sitios.
//
// Concepto: "cuadrar". Un cuadrado al que le falta una pieza (el cuerpo, en
// terracota) y la pieza que lo completa (la ficha, en dorado, con el check).
// Cuando la ficha encaja, el cuadrado queda completo: las cuentas cuadran.
// La esquina superior derecha, grande y redonda, es la firma de la marca y se
// repite en las tarjetas (clase .card-marca).

export const VIEWBOX = 64

// Cuerpo: cuadrado de 52 con una muesca en el cuarto superior derecho.
export const CUERPO =
  'M16 6H29A3 3 0 0 1 32 9V29A3 3 0 0 0 35 32H55A3 3 0 0 1 58 35V48A10 10 0 0 1 48 58H16A10 10 0 0 1 6 48V16A10 10 0 0 1 16 6Z'
// Ficha: la pieza que encaja en la muesca, con 3 unidades de holgura.
export const FICHA = 'M38 6H48A10 10 0 0 1 58 16V26A3 3 0 0 1 55 29H38A3 3 0 0 1 35 26V9A3 3 0 0 1 38 6Z'
// Check dentro de la ficha (señal de cuadre).
export const CHECK = 'M41.5 17.5L45 21L52 13.5'
// Posición "sin encajar" de la ficha (animaciones y estado "por cuadrar").
export const FICHA_FUERA = { x: 14, y: -14 }

export const COLORES = {
  claro: { cuerpo: '#d9622b', ficha: '#d9a441', check: '#221f19', fondo: '#f7f4ee', tinta: '#221f19' },
  oscuro: { cuerpo: '#e8823f', ficha: '#e8bc63', check: '#17140f', fondo: '#17140f', tinta: '#f5f1e8' },
}

// SVG autónomo del isotipo (archivos de marca y sharp).
// variante: 'claro' | 'oscuro' | 'mono' (mono = una sola tinta, check recortado)
export function svgIsotipo({ variante = 'claro', check = true, size = 64, tinta = '#000' } = {}) {
  const mono = variante === 'mono'
  const c = COLORES[variante === 'oscuro' ? 'oscuro' : 'claro']
  const cuerpo = mono ? tinta : c.cuerpo
  const ficha = mono ? tinta : c.ficha
  const mascara =
    mono && check
      ? `<mask id="m"><rect width="64" height="64" fill="#fff"/><path d="${CHECK}" fill="none" stroke="#000" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></mask>`
      : ''
  const checkEl =
    check && !mono
      ? `<path d="${CHECK}" fill="none" stroke="${c.check}" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>`
      : ''
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="${size}" height="${size}" role="img" aria-label="CuadraMe">${mascara}<path d="${CUERPO}" fill="${cuerpo}"/><path d="${FICHA}" fill="${ficha}"${mascara ? ' mask="url(#m)"' : ''}/>${checkEl}</svg>`
}
