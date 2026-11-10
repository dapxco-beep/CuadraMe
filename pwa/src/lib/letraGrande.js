// «Letra grande»: sube el tamaño base (html) a 112,5 %. Todo lo que va en rem crece junto.
// Se guarda en localStorage y se aplica al arrancar, antes de pintar, para que no parpadee.
const CLAVE = 'cuadrame:letra-grande'

export function leerLetraGrande() {
  try { return localStorage.getItem(CLAVE) === '1' } catch { return false }
}

export function aplicarLetraGrande(activa) {
  try { document.documentElement.style.fontSize = activa ? '112.5%' : '' } catch { /* sin documento */ }
}

export function guardarLetraGrande(activa) {
  try { localStorage.setItem(CLAVE, activa ? '1' : '0') } catch { /* sin almacenamiento */ }
  aplicarLetraGrande(activa)
}

export function iniciarLetraGrande() {
  aplicarLetraGrande(leerLetraGrande())
}
