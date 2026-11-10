// Vibración corta como respuesta al tocar. Si el aparato no vibra (iPhone, escritorio, pruebas)
// no pasa nada: cada función protege la llamada.
function vibrar(patron) {
  try {
    if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') navigator.vibrate(patron)
  } catch { /* sin vibración */ }
}

export const toque = () => vibrar(10)
export const exito = () => vibrar([15, 40, 15])
export const error = () => vibrar([60, 40, 60])
