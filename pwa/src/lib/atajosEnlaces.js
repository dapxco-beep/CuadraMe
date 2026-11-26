// Atajos ya armados y FIRMADOS, alojados en /descargas (public/descargas): no dependen de enlaces de iCloud. Al tocarlos en Safari el iPhone ofrece «Agregar atajo»: la persona NO construye nada, solo los instala y, cuando iOS le pregunta
// «Pega tu clave de CuadraMe», pega su clave. Si un enlace cambia, quien ya instaló el atajo conserva su versión:
// hay que pegar el nuevo aquí. El nombre con el que se comparte cada atajo debe ser EXACTAMENTE el que dice la guía.

// «CuadraMe Apple Pay»: la automatización «Transacción» le entrega comercio, monto y tarjeta.
export const ATAJO_ICLOUD_URL = 'https://www.icloud.com/shortcuts/aa83c98605844140a50c8232344f0317'
// «CuadraMe Notificaciones» (iOS 27, disparador «Cuando recibo una notificación»): lee los avisos de Nequi, Nu, etc.
export const ATAJO_NOTIFICACIONES_URL = 'https://www.icloud.com/shortcuts/5c8ebb727bdf450daae624427b4221f6' // desde 2026-11-24 es el MISMO atajo que Registrar (avisos + gesto)
// «CuadraMe Registrar»: un gesto toma un pantallazo del comprobante y lee su texto (para bancos que no avisan al enviar).
export const ATAJO_REGISTRAR_URL = 'https://www.icloud.com/shortcuts/5c8ebb727bdf450daae624427b4221f6'
// Respaldo: los mismos atajos como archivo firmado (descarga directa desde Safari).
export const ATAJO_ARCHIVO_APPLE_PAY = '/descargas/CuadraMe%20Apple%20Pay.shortcut'
export const ATAJO_ARCHIVO_REGISTRAR = '/descargas/CuadraMe%20Registrar.shortcut'
// Última vez que los atajos cambiaron de forma que conviene reinstalarlos. iOS NO actualiza los atajos instalados y la app no puede
// saber qué versión tiene cada persona, así que el catálogo muestra un aviso (que cada quien cierra) cuando esta fecha cambia.
// Al publicar atajos nuevos: cambia `version` (y `fecha`) para que el aviso vuelva a salir.
export const ATAJOS_ACTUALIZADOS = { version: '2026-11-24', fecha: '24 de noviembre de 2026' }
// La app de Android («CuadraMe Captura») se descarga de aquí mismo, sin tiendas ni terceros.
export const APK_URL = '/descargas/cuadrame-captura.apk'
