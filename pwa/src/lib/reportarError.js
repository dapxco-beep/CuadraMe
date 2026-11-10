// Sentry se descarga solo si hay DSN (producción): así el paquete principal no lo
// arrastra. DSN vacío = monitoreo desactivado, sin romper nada. Los errores que
// ocurran antes de que termine de cargar se guardan y se envían al terminar.
// La descarga empieza DESPUÉS del primer pintado (no compite con lo que la persona ve primero).
let sentry = null
const pendientes = []
function cargarSentry() {
  import('@sentry/react')
    .then((S) => {
      S.init({
        dsn: import.meta.env.VITE_SENTRY_DSN,
        environment: import.meta.env.MODE,
        tracesSampleRate: 0.1,
        sendDefaultPii: false,
      })
      sentry = S
      pendientes.splice(0).forEach(([e, info]) => S.captureException(e, info))
    })
    .catch(() => {})
}

if (import.meta.env.VITE_SENTRY_DSN) {
  if (typeof window === 'undefined' || typeof requestAnimationFrame !== 'function') cargarSentry()
  else requestAnimationFrame(() => setTimeout(cargarSentry, 0)) // tras el primer cuadro pintado
}

export function reportar(error, info) {
  if (sentry) sentry.captureException(error, info)
  else if (import.meta.env.VITE_SENTRY_DSN) pendientes.push([error, info])
}
