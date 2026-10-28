import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, Download, ShieldCheck, Trash2, Upload } from 'lucide-react'
import { api } from '../lib/api'
import { useDialogos } from '../lib/DialogosContext'
import { desactivarPush } from '../lib/push'
import BorrarMiCuenta from './BorrarMiCuenta'
import ImportarRespaldo from './ImportarRespaldo'
import { FINALIDADES, formatearFechaCO, ORDEN_OPCIONALES, VERSION_TEXTOS } from '../lib/consentimientos'

// Perfil -> "Privacidad y datos": ver y revocar cada autorización, descargar mis datos
// y eliminar mi cuenta. Revocar NO borra el historial: agrega un registro nuevo.
export default function SeccionPrivacidad({ onEliminarCuenta, eliminando }) {
  const { confirmar, avisar } = useDialogos()
  const [estado, setEstado] = useState(null)
  const [historial, setHistorial] = useState(null)
  const [ocupado, setOcupado] = useState('')
  const [borrando, setBorrando] = useState(false)
  const [importando, setImportando] = useState(false)

  function cargar() {
    Promise.resolve().then(() => api.consentimientos()).then(setEstado).catch(() => {})
  }
  useEffect(cargar, [])

  async function cambiar(finalidad, aceptado) {
    if (!aceptado) {
      const ok = await confirmar(
        'Dejaremos de usar tus datos para esto. Queda anotado y puedes volver a darnos el permiso cuando quieras.',
        { titulo: `¿Quitar el permiso de «${FINALIDADES[finalidad].titulo}»?`, confirmarTexto: 'Quitar permiso', peligro: true }
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
      avisar(err.message || 'No pudimos guardar el cambio. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setOcupado('')
    }
  }

  async function verHistorial() {
    if (historial) return setHistorial(null)
    try {
      setHistorial(await api.historialConsentimientos())
    } catch (err) {
      avisar(err.message || 'No pudimos cargar el historial. Revisa tu conexión e intenta de nuevo.')
    }
  }

  async function descargar() {
    try {
      await api.descargarMisDatos()
    } catch (err) {
      avisar(err.message || 'No pudimos descargar tus datos. Revisa tu conexión e intenta de nuevo.')
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
              Necesaria para usar CuadraMe · la aceptaste el {formatearFechaCO(fin.tratamiento_basico.fecha_co)} · versión {fin.tratamiento_basico.version}.
              Para quitarla, borra tu cuenta (abajo).
            </p>
          </div>
        )}
        {fin &&
          ORDEN_OPCIONALES.map((f) => {
            const x = fin[f] || { aceptado: false }
            return (
              <div key={f} className="px-4 py-3.5 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{FINALIDADES[f].titulo}</p>
                  <p className="text-xs text-ink-soft mt-0.5">
                    {x.aceptado ? 'Con tu permiso' : x.fecha_co ? 'Permiso quitado' : 'Sin tu permiso'}
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
          <p className="flex-1 text-sm font-medium">Historial de mis permisos</p>
          <ChevronRight size={16} className={`text-ink-soft transition-transform ${historial ? 'rotate-90' : ''}`} />
        </button>
        {historial && (
          <ul className="px-4 py-3 space-y-1.5 text-xs text-ink-soft">
            {historial.length === 0 && <li>Aún no has dado ni quitado ningún permiso.</li>}
            {historial.map((h) => (
              <li key={h.id}>
                {formatearFechaCO(h.fecha_co)} · {FINALIDADES[h.finalidad]?.titulo || h.finalidad} · {h.aceptado ? 'diste permiso' : 'quitaste el permiso'} (versión {h.version})
              </li>
            ))}
          </ul>
        )}
        <button onClick={descargar} className="w-full flex items-center gap-3 px-4 py-3.5 text-left">
          <Download size={20} className="text-accent shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium">Descargar mis datos</p>
            <p className="text-xs text-ink-soft mt-0.5">Un archivo con todo lo que CuadraMe guarda de ti. Lo puedes abrir en Excel.</p>
          </div>
        </button>
        <button onClick={() => setImportando(true)} className="w-full flex items-center gap-3 px-4 py-3.5 text-left">
          <Upload size={20} className="text-accent shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium">Importar mi respaldo</p>
            <p className="text-xs text-ink-soft mt-0.5">Recupera lo que descargaste antes. Primero ves cómo quedaría y puedes deshacerlo.</p>
          </div>
        </button>
        <Link to="/legal/autorizacion-datos" className="flex items-center gap-3 px-4 py-3.5">
          <p className="flex-1 text-sm font-medium">Leer los textos legales</p>
          <ChevronRight size={16} className="text-ink-soft" />
        </Link>
        <button
          onClick={() => setBorrando(true)}
          disabled={eliminando}
          className="w-full flex items-center gap-3 px-4 py-3.5 text-left text-danger disabled:opacity-60"
        >
          <Trash2 size={20} className="shrink-0" />
          <p className="flex-1 text-sm font-medium">{eliminando ? 'Borrando...' : 'Borrar mi cuenta y todos mis datos'}</p>
        </button>
      </div>

      {importando && <ImportarRespaldo onCerrar={() => setImportando(false)} />}

      {borrando && (
        <BorrarMiCuenta
          eliminando={eliminando}
          onCancelar={() => setBorrando(false)}
          onDescargar={descargar}
          onConfirmar={(palabra) => onEliminarCuenta(palabra)}
        />
      )}
    </section>
  )
}
