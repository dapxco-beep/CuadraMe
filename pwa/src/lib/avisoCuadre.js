// Aviso «una cuenta no cuadra con tu banco» del Inicio: se puede ocultar y no vuelve MIENTRAS LA DIFERENCIA SEA LA MISMA.
// Si la diferencia cambia (otro monto u otro mes), la clave cambia y el aviso vuelve a salir. Se guarda en este dispositivo
// (solo claves de texto, sin datos sensibles), igual que los recordatorios descartados.

const LLAVE = 'cuadrame:cuadre-ocultos'

/** Una clave por cuenta + mes + diferencia (redondeada a pesos). */
export function claveCuadre(c) {
  return `${c.cuenta_id}:${c.mes}:${Math.round(Math.abs(Number(c.diferencia) || 0))}`
}

export function leerOcultos() {
  try {
    const v = JSON.parse(localStorage.getItem(LLAVE) || '[]')
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

export function guardarOcultos(claves) {
  try {
    localStorage.setItem(LLAVE, JSON.stringify(claves))
  } catch {
    /* sin almacenamiento: el aviso reaparece al recargar, no pasa nada */
  }
}

/**
 * A partir de GET /conciliacion/cuadre/resumen, el aviso que toca mostrar (o null):
 * {n, texto, claves}. Solo cuentan las cuentas `no_cuadra` cuya clave no esté oculta.
 */
export function avisoVisible(resumen, ocultos = []) {
  const malas = (resumen?.cuentas || []).filter((c) => c.estado === 'no_cuadra' && !ocultos.includes(claveCuadre(c)))
  if (!malas.length) return null
  const p = malas[0]
  const t = p.texto || ''
  return {
    n: malas.length,
    texto: `${p.cuenta}: ${t.charAt(0).toLowerCase()}${t.slice(1)}`,
    claves: malas.map(claveCuadre),
  }
}
