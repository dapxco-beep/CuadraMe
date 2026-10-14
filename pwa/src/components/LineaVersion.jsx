import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { APP_BUILD, APP_COMMIT, APP_VERSION, textoVersion } from '../lib/version'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Línea discreta con la versión de la app, para quien da soporte. No usa router ni contextos:
// también vive en la pantalla de error. Al tocar el texto 5 veces muestra más detalle.
export default function LineaVersion({ className = '' }) {
  const [toques, setToques] = useState(0)
  const [copiado, setCopiado] = useState(false)
  const [detalle, setDetalle] = useState(null)
  const texto = textoVersion()

  async function cargarDetalle() {
    const d = { entorno: import.meta.env.MODE, sw: 'no disponible', servidor: 'sin respuesta' }
    try {
      const reg = await navigator.serviceWorker?.getRegistration?.()
      d.sw = reg?.waiting ? 'en espera' : reg?.active ? 'activo' : 'sin registrar'
    } catch { /* nada */ }
    try {
      const r = await fetch(`${API_URL}/version`)
      if (r.ok) {
        const s = await r.json()
        d.servidor = `${s.version} · ${s.commit}`
      }
    } catch { /* sin conexión */ }
    setDetalle(d)
  }

  function tocar() {
    const n = toques + 1
    setToques(n)
    if (n === 5) cargarDetalle()
  }

  async function copiar() {
    const extra = detalle ? ` · Servidor: ${detalle.servidor} · Service worker: ${detalle.sw} · Entorno: ${detalle.entorno}` : ''
    try {
      await navigator.clipboard.writeText(texto + extra)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2000)
    } catch { /* sin permiso de portapapeles */ }
  }

  return (
    <div className={`flex flex-col items-center gap-1 ${className}`} data-version={`${APP_VERSION}|${APP_BUILD}|${APP_COMMIT}`}>
      <div className="flex items-center justify-center gap-1 flex-wrap">
        <span className="text-[11px] text-ink-soft" onClick={tocar} data-testid="linea-version">{texto}</span>
        <button type="button" onClick={copiar} className="inline-flex items-center gap-1 text-[11px] text-accent font-medium min-h-[32px] px-2">
          {copiado ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
          {copiado ? 'Copiado' : 'Copiar'}
        </button>
      </div>
      {detalle && (
        <ul className="text-[11px] text-ink-soft text-center" data-testid="detalle-version">
          <li>Servidor: {detalle.servidor}</li>
          <li>Service worker: {detalle.sw}</li>
          <li>Entorno: {detalle.entorno}</li>
        </ul>
      )}
    </div>
  )
}
