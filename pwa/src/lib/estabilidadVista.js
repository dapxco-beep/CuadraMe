// Estabilidad de la vista: la app se comporta como una app nativa, sin que un pellizco o un
// doble toque la dejen «agrandada» y descuadrada.
//
// El doble toque NO se frena aquí a propósito: cancelar `touchend` también cancelaría el clic y se
// perderían toques rápidos legítimos (teclado numérico, +/-). Eso lo resuelve `touch-action: manipulation`.
//
// Capas (cada una cubre un navegador distinto):
//   1. <meta viewport maximum-scale=1, user-scalable=no>  → Android/Chrome y la mayoría de WebViews.
//   2. CSS `touch-action: manipulation` + campos de 16 px (index.css) → sin zoom por doble toque ni
//      zoom automático de iOS al enfocar un campo.
//   3. Este archivo → iOS Safari (y la app instalada), que ignora user-scalable=no por accesibilidad
//      y solo se deja frenar escuchando `gesturestart` / un toque de dos dedos sobre la página.
//
// Accesibilidad: NO se toca el tamaño de texto del sistema ni del navegador (no se fija ningún px en
// <html>; los tamaños salen de rem). Lo único que se desactiva es el zoom de página por gesto. Quien
// necesite letra más grande la sube en Ajustes del teléfono (Texto y tamaño de pantalla) o en el
// navegador, y la app la sigue.

/** Frena el zoom por pellizco sin tocar el scroll de un dedo ni los toques. Devuelve cómo deshacerlo. */
export function bloquearZoomPellizco(doc = typeof document !== 'undefined' ? document : null) {
  if (!doc) return () => {}
  const evitar = (e) => {
    if (e.cancelable) e.preventDefault()
  }
  // Safari iOS: eventos propios del pellizco.
  const gestos = ['gesturestart', 'gesturechange', 'gestureend']
  gestos.forEach((g) => doc.addEventListener(g, evitar, { passive: false }))

  // Dos dedos o escala distinta de 1: pellizco. Un dedo (scroll) pasa sin tocar.
  const alMover = (e) => {
    if ((e.touches && e.touches.length > 1) || (typeof e.scale === 'number' && e.scale !== 1)) evitar(e)
  }
  doc.addEventListener('touchmove', alMover, { passive: false })

  return () => {
    gestos.forEach((g) => doc.removeEventListener(g, evitar))
    doc.removeEventListener('touchmove', alMover)
  }
}
