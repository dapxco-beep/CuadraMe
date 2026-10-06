import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ShieldCheck, X } from 'lucide-react'
import { api } from '../lib/api'
import { FINALIDADES, VERSION_TEXTOS } from '../lib/consentimientos'

// Consentimiento ESPECÍFICO de una finalidad opcional (lectura de correo, IA...).
// Se muestra justo antes de usar la función. La casilla NO viene marcada: hay que
// marcarla para poder autorizar, y "Ahora no" no registra nada.
export default function ModalConsentimiento({ finalidad, onAceptado, onCancelar, origen = 'app' }) {
  const info = FINALIDADES[finalidad]
  const [acepta, setAcepta] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  if (!info) return null

  async function autorizar() {
    setGuardando(true)
    setError('')
    try {
      await api.guardarConsentimientos(VERSION_TEXTOS, [{ finalidad, aceptado: true }], origen)
      onAceptado?.()
    } catch (err) {
      setError(err.message || 'No se pudo guardar tu autorización')
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-[60] sheet-backdrop" role="dialog" aria-modal="true" aria-label="Autorización específica">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8 max-h-[90vh] overflow-y-auto sheet-content">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <ShieldCheck size={18} className="text-accent" /> Necesitamos tu autorización
          </h2>
          <button onClick={onCancelar} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>
        <p className="text-sm font-semibold">{info.titulo}</p>
        <p className="text-sm text-ink-soft mt-1.5 leading-relaxed">{info.texto}</p>

        <label className="flex items-start gap-3 mt-4 text-sm">
          <input
            type="checkbox"
            checked={acepta}
            onChange={(e) => setAcepta(e.target.checked)}
            className="mt-1 w-4 h-4 accent-accent shrink-0"
          />
          <span>
            Lo autorizo de forma libre, previa e informada. Entiendo que puedo revocarlo cuando quiera desde Perfil → Privacidad y datos.
          </span>
        </label>
        <p className="text-xs text-ink-soft mt-2">
          Más detalle en la{' '}
          <Link to="/legal/autorizacion-datos" className="text-accent font-medium">Autorización de datos</Link> y la{' '}
          <Link to="/legal/privacidad" className="text-accent font-medium">Política de Privacidad</Link>.
        </p>

        {error && <p role="alert" className="text-sm text-danger mt-3">{error}</p>}

        <button
          onClick={autorizar}
          disabled={!acepta || guardando}
          className="w-full mt-4 bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-50"
        >
          {guardando ? 'Guardando...' : 'Autorizo'}
        </button>
        <button onClick={onCancelar} className="w-full mt-2 py-3 text-sm text-ink-soft font-medium">
          Ahora no
        </button>
      </div>
    </div>
  )
}
