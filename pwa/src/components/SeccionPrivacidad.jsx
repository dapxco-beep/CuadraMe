import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, Download, ShieldCheck, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { useDialogos } from '../lib/DialogosContext'
import { desactivarPush } from '../lib/push'
import { FINALIDADES, formatearFechaCO, ORDEN_OPCIONALES, VERSION_TEXTOS } from '../lib/consentimientos'

// Perfil -> "Privacidad y datos": ver y revocar cada autorización, descargar mis datos
// y eliminar mi cuenta. Revocar NO borra el historial: agrega un registro nuevo.
export default function SeccionPrivacidad({ onEliminarCuenta, eliminando }) {
  const { confirmar, avisar } = useDialogos()
  const [estado, setEstado] = useState(null)
  const [historial, setHistorial] = useState(null)
  const [ocupado, setOcupado] = useState('')

  function cargar() {
    Promise.resolve().then(() => api.consentimientos()).then(setEstado).catch(() => {})
  }
  useEffect(cargar, [])

  async function cambiar(finalidad, aceptado) {
    if (!aceptado) {
      const ok = await confirmar(
        'Dejaremos de tratar tus datos para esta finalidad. Queda registrado, y puedes volver a autorizarlo cuando quieras.',
        { titulo: `¿Revocar «${FINALIDADES[finalidad].titulo}»?`, confirmarTexto: 'Revocar', peligro: true }
      )
      if (!ok) return
    }
    setOcupado(finalidad)
    try {
      await api.guardarConsentimientos(VERSION_TEXTOS, [{ finalidad, aceptado }], 'perfil')
      if (!aceptado) {
        // Revocar tiene efecto real, no solo un registro.
        if (finalidad === 'lectura_correo') await api.gmailDesconectar().catch(() => {})
        if (finalidad === 'notificaciones') await desactivarPush().catch(() => {})
      }
      cargar()
      setHistorial(null)
    } catch (err) {
      avisar(err.message || 'No se pudo guardar el cambio')
    } finally {
      setOcupado('')
    }
  }

  async function verHistorial() {
    if (historial) return setHistorial(null)
    try {
      setHistorial(await api.historialConsentimientos())
    } catch (err) {
      avisar(err.message || 'No se pudo cargar el historial')
    }
  }

  async function descargar() {
    try {
      await api.exportarExcel()
    } catch (err) {
      avisar(err.message || 'No se pudo descargar tus datos')
    }
  }

  const fin = estado?.finalidades
  return (
    <section className="mx-6 mt-6" aria-label="Privacidad y datos">
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheck size={16} className="text-ink-soft" />
        <h2 className="text-[15px] font-semibold">Privacidad y datos</h2>
      </div>

      <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line">
        {fin && (
          <div className="px-4 py-3.5">
            <p className="text-sm font-medium">{FINALIDADES.tratamiento_basico.titulo}</p>
            <p className="text-xs text-ink-soft mt-0.5">
              Obligatoria para usar CuadraMe · aceptada {formatearFechaCO(fin.tratamiento_basico.fecha_co)} · versión {fin.tratamiento_basico.version}.
              Para revocarla, elimina tu cuenta (abajo).
            </p>
          </div>
        )}
        {fin &&
          ORDEN_OPCIONALES.map((f) => {
            const x = fin[f]
            return (
              <div key={f} className="px-4 py-3.5 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{FINALIDADES[f].titulo}</p>
                  <p className="text-xs text-ink-soft mt-0.5">
                    {x.aceptado ? 'Autorizado' : x.fecha_co ? 'Revocado' : 'No autorizado'}
                    {x.fecha_co ? ` · ${formatearFechaCO(x.fecha_co)}` : ''}
                  </p>
                </div>
                <button
                  role="switch"
                  aria-checked={x.aceptado}
                  aria-label={FINALIDADES[f].titulo}
                  disabled={ocupado === f}
                  onClick={() => cambiar(f, !x.aceptado)}
                  className={`shrink-0 w-12 h-7 rounded-full transition-colors relative ${x.aceptado ? 'bg-accent' : 'bg-ink-soft/35'} disabled:opacity-60`}
                >
                  <span className={`absolute top-0.5 left-0 w-6 h-6 rounded-full bg-white shadow transition-transform ${x.aceptado ? 'translate-x-5' : 'translate-x-0.5'}`} />
                </button>
              </div>
            )
          })}
        <button onClick={verHistorial} className="w-full flex items-center gap-3 px-4 py-3.5 text-left">
          <p className="flex-1 text-sm font-medium">Historial de mis autorizaciones</p>
          <ChevronRight size={16} className={`text-ink-soft transition-transform ${historial ? 'rotate-90' : ''}`} />
        </button>
        {historial && (
          <ul className="px-4 py-3 space-y-1.5 text-xs text-ink-soft">
            {historial.length === 0 && <li>Aún no has aceptado ni cancelado ninguna autorización.</li>}
            {historial.map((h) => (
              <li key={h.id}>
                {formatearFechaCO(h.fecha_co)} · {FINALIDADES[h.finalidad]?.titulo || h.finalidad} · {h.aceptado ? 'autorizó' : 'revocó'} (v{h.version})
              </li>
            ))}
          </ul>
        )}
        <button onClick={descargar} className="w-full flex items-center gap-3 px-4 py-3.5 text-left">
          <Download size={20} className="text-accent shrink-0" />
          <p className="flex-1 text-sm font-medium">Descargar mis datos (Excel)</p>
        </button>
        <Link to="/legal/autorizacion-datos" className="flex items-center gap-3 px-4 py-3.5">
          <p className="flex-1 text-sm font-medium">Ver textos legales</p>
          <ChevronRight size={16} className="text-ink-soft" />
        </Link>
        <button
          onClick={onEliminarCuenta}
          disabled={eliminando}
          className="w-full flex items-center gap-3 px-4 py-3.5 text-left text-danger disabled:opacity-60"
        >
          <Trash2 size={20} className="shrink-0" />
          <p className="flex-1 text-sm font-medium">{eliminando ? 'Eliminando...' : 'Eliminar mi cuenta y mis datos'}</p>
        </button>
      </div>
    </section>
  )
}
