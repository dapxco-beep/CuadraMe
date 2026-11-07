// Capturas REALES de pantalla (iPhone y Android) para la guía de los atajos. Mientras un atajo no tenga capturas aquí,
// la guía muestra un dibujo propio (SVG) de esa pantalla. Cuando haya capturas reales, se usan en su lugar.
//
// Cómo agregarlas: guarda las imágenes en `pwa/public/guia/` (mejor .webp o .png de ~800 px de ancho, sin datos
// personales: borra o tapa nombres, montos y números de cuenta) y anótalas aquí:
//
//   'notificaciones': [{ src: '/guia/notificaciones-1.webp', alt: 'Atajos > Automatización > Cuando recibo una notificación' }],
//
// La clave es el `id` del atajo en components/CatalogoAtajos.jsx: apple-pay, notificaciones, registrar, cierre.
// Si el atajo tiene varias capturas, se muestran en ese orden, una por paso.
export const CAPTURAS_REALES = {}
