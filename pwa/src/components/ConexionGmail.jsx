import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronDown, Mail, ShieldCheck } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { useDialogos } from '../lib/DialogosContext'
import ModalConsentimiento from './ModalConsentimiento'

/**
 * Conectar o desconectar Gmail. Sincronizar lo hace el botón «Sincronizar todo» del centro (y su
 * barra de progreso): aquí no hay un segundo botón igual.
 *   estado: GET /correos/gmail/estado   ·   onCambio(): recarga el centro
 */
export default function ConexionGmail({ estado, onCambio }) {
  const { confirmar } = useDialogos()
  const usuario = useAuth()?.usuario
  const [params] = useSearchParams()
  const [pedirConsentimiento, setPedirConsentimiento] = useState(false)
  const [mostrarGuia, setMostrarGuia] = useState(false)
  const [copiado, setCopiado] = useState(false)
  const [error, setError] = useState('')
  // Google devuelve a la app con ?gmail=sin_acceso cuando el correo no está autorizado (modo Pruebas).
  const sinAcceso = params.get('gmail') === 'sin_acceso'

  async function conectar(yaConsentido = false) {
    setError('')
    // Ley 1581: sin la autorización específica de lectura de correo no se conecta.
    if (estado?.consentimiento === false && yaConsentido !== true) {
      setPedirConsentimiento(true)
      return
    }
    try {
      const { url } = await api.gmailConectar()
      window.location.href = url
    } catch (err) {
      setError(err.message || 'No se pudo iniciar la conexión con Gmail')
    }
  }

  async function desconectar() {
    const ok = await confirmar('Se dejarán de sincronizar tus correos bancarios.', {
      titulo: '¿Desconectar Gmail?',
      confirmarTexto: 'Desconectar',
      peligro: true,
    })
    if (!ok) return
    try {
      await api.gmailDesconectar()
      onCambio?.()
    } catch (err) {
      setError(err.message || 'No se pudo desconectar')
    }
  }

  async function copiarCorreo() {
    try {
      await navigator.clipboard.writeText(usuario?.email || '')
      setCopiado(true)
    } catch {
      /* sin portapapeles: queda el botón de correo */
    }
  }

  return (
    <div>
      {!estado?.conectado && (sinAcceso || estado?.modo_pruebas) && (
        <div role="status" className="mb-3 rounded-2xl bg-accent-soft border border-accent/30 p-4" data-testid="aviso-invitacion">
          <p className="text-sm font-semibold">Gmail aún es por invitación</p>
          <p className="text-xs text-ink-soft mt-1 leading-relaxed">
            {sinAcceso ? 'Google no te dejó entrar: tu correo todavía no está en la lista. ' : 'Por ahora solo entran correos que agregamos a mano. '}
            Pídenos que agreguemos el tuyo{usuario?.email ? ` (${usuario.email})` : ''}.
          </p>
          <div className="flex gap-2 mt-3">
            <a
              href={`mailto:${estado?.soporte_email || 'dapxco@gmail.com'}?subject=${encodeURIComponent('Quiero conectar Gmail en CuadraMe')}&body=${encodeURIComponent(`Hola, por favor agreguen mi correo de Gmail para probar CuadraMe: ${usuario?.email || ''}`)}`}
              className="flex-1 text-center bg-ink text-paper font-semibold rounded-xl py-2.5 text-sm"
            >
              Pedir acceso
            </a>
            <button onClick={copiarCorreo} className="px-4 rounded-xl border border-line bg-paper text-sm font-medium">
              {copiado ? 'Copiado' : 'Copiar mi correo'}
            </button>
          </div>
        </div>
      )}

      {pedirConsentimiento && (
        <ModalConsentimiento
          finalidad="lectura_correo"
          origen="flujo_gmail"
          onCancelar={() => setPedirConsentimiento(false)}
          onAceptado={() => {
            setPedirConsentimiento(false)
            conectar(true)
          }}
        />
      )}

      {estado?.conectado ? (
        <div className="rounded-2xl bg-paper border border-line p-4">
          <div className="flex items-center gap-3">
            <Mail size={20} className="text-accent shrink-0" aria-hidden="true" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate">{estado.email}</p>
              <p className="text-xs text-ink-soft">Conectado · solo lectura</p>
            </div>
            <button onClick={desconectar} className="shrink-0 px-3 min-h-[40px] rounded-xl border border-line text-xs font-semibold text-ink-soft">
              Desconectar
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl bg-paper border border-line p-4">
          <p className="text-sm font-semibold">Conecta tu Gmail</p>
          <p className="text-xs text-ink-soft mt-1 mb-3">
            Busco solo los correos de tus bancos y billeteras. Tú apruebas cada movimiento.
          </p>
          <button onClick={() => conectar()} className="w-full bg-ink text-paper font-semibold rounded-xl py-3 text-sm">
            Conectar Gmail
          </button>
        </div>
      )}

      {error && <p className="text-xs text-danger mt-2" role="alert">{error}</p>}

      <p className="flex items-start gap-1.5 text-[11px] text-ink-soft mt-3">
        <ShieldCheck size={16} className="shrink-0 mt-0.5 text-accent" aria-hidden="true" />
        <span>
          Solo tengo permiso de <b>lectura</b>: no envío, borro ni modifico correos. No guardo tus correos ni los PDF, solo
          banco, periodo y estado de cada extracto, y los movimientos que apruebas.
        </span>
      </p>

      <button
        onClick={() => setMostrarGuia((v) => !v)}
        aria-expanded={mostrarGuia}
        className="w-full flex items-center justify-between text-xs text-ink-soft py-2 mt-1"
      >
        <span>(Opcional) Etiqueta «gastos» para correos que no detecto solo</span>
        <ChevronDown size={16} className={`shrink-0 transition-transform ${mostrarGuia ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      {mostrarGuia && (
        <ol className="rounded-2xl bg-paper border border-line divide-y divide-line overflow-hidden">
          {[
            'Abre Gmail y busca un correo de tu banco (ej. de Bancolombia o Nequi).',
            'Ábrelo y toca el ícono de etiqueta o los tres puntos «Más».',
            'Elige «Crear nueva» y escribe exactamente: gastos',
            'Listo: cada correo que quieras que lea, etiquétalo igual.',
          ].map((paso, i) => (
            <li key={i} className="flex items-start gap-3 px-4 py-3">
              <span className="w-5 h-5 rounded-full bg-accent-soft text-accent text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                {i + 1}
              </span>
              <p className="text-xs">{paso}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
