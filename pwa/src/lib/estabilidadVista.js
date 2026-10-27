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

/** ¿Algún ancestro de `el` se desliza de lado a propósito (tabla, carrusel)? Entonces el gesto horizontal es suyo. */
function dentroDeDeslizableLateral(el) {
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
    const ov = typeof getComputedStyle === 'function' ? getComputedStyle(n).overflowX : ''
    if ((ov === 'auto' || ov === 'scroll') && n.scrollWidth > n.clientWidth) return true
  }
  return false
}

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

  // Un dedo que arrastra de lado fuera de una tabla/carrusel NO debe mover la página (en iOS y Android
  // instalada se «corre» hacia los lados). El arrastre vertical y los deslizables laterales pasan intactos.
  let inicio = null
  const alTocar = (e) => {
    const t = e.touches && e.touches.length === 1 ? e.touches[0] : null
    inicio = t ? { x: t.clientX, y: t.clientY, el: e.target } : null
  }
  const alArrastrar = (e) => {
    if (!inicio || !e.touches || e.touches.length !== 1) return
    const dx = e.touches[0].clientX - inicio.x
    const dy = e.touches[0].clientY - inicio.y
    if (Math.abs(dx) > 6 && Math.abs(dx) > Math.abs(dy) && !dentroDeDeslizableLateral(inicio.el)) evitar(e)
  }
  doc.addEventListener('touchstart', alTocar, { passive: true })
  doc.addEventListener('touchmove', alArrastrar, { passive: false })

  return () => {
    doc.removeEventListener('touchstart', alTocar)
    doc.removeEventListener('touchmove', alArrastrar)
    gestos.forEach((g) => doc.removeEventListener(g, evitar))
    doc.removeEventListener('touchmove', alMover)
  }
}
