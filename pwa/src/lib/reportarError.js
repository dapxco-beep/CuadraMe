// Sentry se descarga solo si hay DSN (producción): así el paquete principal no lo
// arrastra. DSN vacío = monitoreo desactivado, sin romper nada. Los errores que
// ocurran antes de que termine de cargar se guardan y se envían al terminar.
let sentry = null
const pendientes = []
if (import.meta.env.VITE_SENTRY_DSN) {
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

export function reportar(error, info) {
  if (sentry) sentry.captureException(error, info)
  else if (import.meta.env.VITE_SENTRY_DSN) pendientes.push([error, info])
}
