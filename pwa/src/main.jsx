import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
import './index.css'
import App from './App.jsx'

// DSN vacío = monitoreo desactivado, sin romper nada — así el DSN se puede
// dejar sin configurar en local/preview y solo activarse en producción.
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  })
}

function PantallaError() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 px-8 text-center">
      <p className="text-sm font-semibold">Algo salió mal</p>
      <p className="text-sm text-ink-soft">
        Ya nos llegó el aviso. Intenta recargar la app.
      </p>
      <button
        onClick={() => window.location.reload()}
        className="mt-2 text-sm text-accent font-medium"
      >
        Recargar
      </button>
    </div>
  )
}

// El service worker (public/sw.js) da notificaciones push y un caché del shell
// de la app para abrirla sin conexión. En desarrollo se omite: cachear archivos
// mientras se programa hace que los cambios "no aparezcan".
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Sentry.ErrorBoundary fallback={<PantallaError />}>
      <App />
    </Sentry.ErrorBoundary>
  </StrictMode>,
)
