import { Component, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Sora autoalojada (solo el subconjunto latin; cubre español). Antes se pedía a Google
// Fonts: cada visita le contaba a un tercero que el usuario abría una app de finanzas
// (Ley 1581) y bloqueaba el primer pintado. font-display: swap viene en estos CSS.
import '@fontsource/sora/latin-400.css'
import '@fontsource/sora/latin-500.css'
import '@fontsource/sora/latin-600.css'
import '@fontsource/sora/latin-700.css'
import '@fontsource/sora/latin-800.css'
import './index.css'
import App from './App.jsx'
import { iniciarInstalacion } from './lib/instalarPwa'
import LineaVersion from './components/LineaVersion'
import { bloquearZoomPellizco } from './lib/estabilidadVista'

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

function reportar(error, info) {
  if (sentry) sentry.captureException(error, info)
  else if (import.meta.env.VITE_SENTRY_DSN) pendientes.push([error, info])
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
      <LineaVersion className="mt-4" />
    </div>
  )
}

class LimiteDeError extends Component {
  state = { fallo: false }
  static getDerivedStateFromError() {
    return { fallo: true }
  }
  componentDidCatch(error, info) {
    reportar(error, { contexts: { react: { componentStack: info?.componentStack } } })
  }
  render() {
    return this.state.fallo ? <PantallaError /> : this.props.children
  }
}

// El service worker (public/sw.js) da notificaciones push y un caché del shell
// de la app para abrirla sin conexión. En desarrollo se omite: cachear archivos
// mientras se programa hace que los cambios "no aparezcan".
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}

// Tras un despliegue, una pestaña abierta puede pedir una pantalla (archivo con hash) que ya no
// existe en el servidor. En vez de la pantalla de error, se recarga UNA vez para traer la versión
// nueva (la marca en sessionStorage evita un bucle si el problema es otro).
window.addEventListener('vite:preloadError', (event) => {
  try {
    if (sessionStorage.getItem('cuadrame_recarga_chunk') === '1') return
    sessionStorage.setItem('cuadrame_recarga_chunk', '1')
    event.preventDefault()
    window.location.reload()
  } catch {
    /* sin almacenamiento: se deja el comportamiento normal */
  }
})
window.addEventListener('load', () => {
  setTimeout(() => {
    try {
      sessionStorage.removeItem('cuadrame_recarga_chunk')
    } catch {
      /* nada */
    }
  }, 10000)
})

bloquearZoomPellizco()

iniciarInstalacion() // guarda el aviso de Chrome para ofrecer «Instalar» con un toque
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <LimiteDeError>
      <App />
    </LimiteDeError>
  </StrictMode>,
)
