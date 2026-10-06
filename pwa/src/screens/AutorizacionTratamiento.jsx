import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { CORREO_RESPONSABLE, DERECHOS, FINALIDADES, ORDEN_OPCIONALES, VERSION_TEXTOS } from '../lib/consentimientos'

// Pantalla formal de "Autorización de tratamiento de datos" (Ley 1581 de 2012).
// Aparece tras el primer inicio de sesión y cada vez que cambia la versión de los textos.
// Casillas SEPARADAS y NO premarcadas: una obligatoria y tres opcionales.
export default function AutorizacionTratamiento({ onListo }) {
  const { logout } = useAuth()
  const [marcas, setMarcas] = useState({ tratamiento_basico: false, lectura_correo: false, ia: false, notificaciones: false })
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function continuar() {
    setGuardando(true)
    setError('')
    try {
      // Una decisión por finalidad (también las opcionales rechazadas quedan registradas).
      const items = Object.entries(marcas).map(([finalidad, aceptado]) => ({ finalidad, aceptado }))
      await api.guardarConsentimientos(VERSION_TEXTOS, items, 'registro')
      onListo()
    } catch (err) {
      setError(err.message || 'No se pudo guardar tu autorización')
      setGuardando(false)
    }
  }

  const casilla = (f) => (
    <label key={f} className="flex items-start gap-3 rounded-2xl border border-line bg-paper-raised p-3.5 text-sm">
      <input
        type="checkbox"
        checked={marcas[f]}
        onChange={(e) => setMarcas((m) => ({ ...m, [f]: e.target.checked }))}
        className="mt-1 w-4 h-4 accent-accent shrink-0"
      />
      <span>
        <b>
          {FINALIDADES[f].titulo} {FINALIDADES[f].obligatoria ? '(obligatoria)' : '(opcional)'}
        </b>
        <span className="block text-xs text-ink-soft mt-1 leading-relaxed">{FINALIDADES[f].texto}</span>
      </span>
    </label>
  )

  return (
    <div className="flex-1 overflow-y-auto pb-10 screen-enter">
      <header className="px-6 pantalla-top pb-2">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <ShieldCheck size={20} className="text-accent" /> Autorización de tratamiento de datos
        </h1>
      </header>

      <div className="px-6 mt-3 space-y-4 text-sm leading-relaxed">
        <p>
          Antes de empezar, queremos que sepas qué hacemos con tu información. En pocas palabras:
        </p>
        <ul className="list-disc pl-5 space-y-1.5 text-ink-soft">
          <li><b className="text-ink">Qué datos:</b> tu nombre y correo, y lo que tú registras (cuentas, movimientos, presupuestos, metas, deudas).</li>
          <li><b className="text-ink">Para qué:</b> darte el servicio de organización y análisis de tus finanzas. No vendemos tus datos.</li>
          <li><b className="text-ink">Tus derechos:</b> {DERECHOS.join(', ')}. Los ejerces desde Perfil → Privacidad y datos o escribiendo al responsable.</li>
          <li><b className="text-ink">Responsable:</b> DAPX · <a className="text-accent font-medium" href={`mailto:${CORREO_RESPONSABLE}`}>{CORREO_RESPONSABLE}</a></li>
        </ul>
        <p className="text-xs">
          Lee los textos completos: <Link to="/legal/terminos" className="text-accent font-medium">Términos y Condiciones</Link>,{' '}
          <Link to="/legal/privacidad" className="text-accent font-medium">Política de Privacidad</Link> y{' '}
          <Link to="/legal/autorizacion-datos" className="text-accent font-medium">Autorización de datos</Link>.
        </p>

        <div className="space-y-2.5" role="group" aria-label="Autorizaciones">
          {casilla('tratamiento_basico')}
          <p className="text-xs text-ink-soft pt-1">Opcionales: puedes cambiarlas cuando quieras y la app funciona sin ellas.</p>
          {ORDEN_OPCIONALES.map(casilla)}
        </div>

        <p className="text-[11px] text-ink-soft">
          Versión {VERSION_TEXTOS} de los textos. Son un borrador pendiente de revisión por un abogado colombiano.
        </p>

        {error && <p role="alert" className="text-sm text-danger">{error}</p>}

        <button
          onClick={continuar}
          disabled={!marcas.tratamiento_basico || guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-50"
        >
          {guardando ? 'Guardando...' : 'Aceptar y continuar'}
        </button>
        <button onClick={logout} className="w-full py-2 text-sm text-ink-soft font-medium">
          No acepto, cerrar sesión
        </button>
      </div>
    </div>
  )
}
