import { useEffect, useState } from 'react'
import { AlertCircle, Mail, Sparkles } from 'lucide-react'
import Icono from './Icono'
import { api } from '../lib/api'
import { resumenEstadoGmail, TEXTO_APRENDIENDO } from '../lib/estadoGmail'

// «Gmail conectado · último extracto leído: 15 oct» + aviso amable si falta un extracto + «estamos aprendiendo tu banco».
// `gmail` y `cuentas` (de sincronizacion/estado) ya los tiene la pantalla; el historial se pide aquí (si falla, solo se
// omite la fecha). Sin conexión o sin datos no muestra nada que asuste.
export default function EstadoGmail({ gmail, cuentas, className = '', soloCorreo = false }) {
  const [historial, setHistorial] = useState([])
  useEffect(() => {
    let activo = true
    Promise.resolve()
      .then(() => api.historialExtractos?.())
      .then((h) => activo && Array.isArray(h) && setHistorial(h))
      .catch(() => {})
    return () => { activo = false }
  }, [])
  // «Movimientos del correo» habla solo de los avisos del banco: nada de extractos ni de bancos por aprender.
  if (soloCorreo) {
    if (!gmail?.conectado) return null
    return (
      <section className={className} aria-label="Estado de Gmail" data-testid="estado-gmail">
        <p className="flex items-center gap-1.5 text-xs text-ink-soft" data-testid="estado-gmail-linea">
          <Icono icono={Mail} tam="sm" /> <span>Gmail conectado · leyendo los avisos de tu banco</span>
        </p>
      </section>
    )
  }
  const r = resumenEstadoGmail({ gmail, historial, cuentas })
  if (!r.linea) return null
  return (
    <section className={className} aria-label="Estado de Gmail" data-testid="estado-gmail">
      <p className="flex items-center gap-1.5 text-xs text-ink-soft" data-testid="estado-gmail-linea">
        <Icono icono={Mail} tam="sm" /> <span>{r.linea}</span>
      </p>
      {r.avisos.map((a) => (
        <p key={a.cuentaId} role="status" className="mt-1.5 flex items-start gap-1.5 rounded-xl bg-accent-soft border border-accent/30 px-3 py-2 text-xs" data-testid="aviso-falta-extracto">
          <Icono icono={AlertCircle} tam="sm" className="mt-px text-accent" /> <span>{a.texto}. Súbelo o mándalo a tu Gmail y yo lo leo.</span>
        </p>
      ))}
      {r.aprendiendo && (
        <p className="mt-1.5 flex items-start gap-1.5 text-xs text-ink-soft" data-testid="aprendiendo-formato">
          <Icono icono={Sparkles} tam="sm" className="mt-px text-accent" /> <span>{TEXTO_APRENDIENDO}</span>
        </p>
      )}
    </section>
  )
}
