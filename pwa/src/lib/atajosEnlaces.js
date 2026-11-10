// Enlaces de iCloud de los atajos ya armados: la persona NO construye nada, solo los instala y, cuando iOS le pregunta
// «Pega tu clave de CuadraMe», pega su clave. Si un enlace cambia, quien ya instaló el atajo conserva su versión:
// hay que pegar el nuevo aquí. El nombre con el que se comparte cada atajo debe ser EXACTAMENTE el que dice la guía.

// «CuadraMe Apple Pay»: la automatización «Transacción» le entrega comercio, monto y tarjeta.
export const ATAJO_ICLOUD_URL = 'https://www.icloud.com/shortcuts/002171858328481ab9b3d58718192c73'
// «CuadraMe Notificaciones» (iOS 27, disparador «Cuando recibo una notificación»): lee los avisos de Nequi, Nu, etc.
export const ATAJO_NOTIFICACIONES_URL = 'https://www.icloud.com/shortcuts/1286c4417c524945809f6dd419538d7f'
// «CuadraMe Registrar»: un gesto toma un pantallazo del comprobante y lee su texto (para bancos que no avisan al enviar).
export const ATAJO_REGISTRAR_URL = 'https://www.icloud.com/shortcuts/145fc78e5f2d4fc1b1b8fe1ad2c94be3'
// La app de Android («CuadraMe Captura») se descarga de aquí mismo, sin tiendas ni terceros.
export const APK_URL = '/descargas/cuadrame-captura.apk'
