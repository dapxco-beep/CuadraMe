import { useState } from 'react'
import { Check, Copy, Download, ExternalLink } from 'lucide-react'
import ClaveAtajo from './ClaveAtajo'
import {
  API_URL, API_URL_VOZ, JSON_CIERRE_APP, JSON_DEL_ATAJO, PASOS_ANDROID, PASOS_VOZ, SCRIPT_ANDROID,
} from '../lib/scriptAndroid'

// Todo lo que NO necesita una persona normal, plegado bajo «Avanzado»: armar los atajos a mano,
// Android con Tasker y el atajo por voz. Cada bloque va en su propio desplegable.

function BotonCopiar({ texto, etiqueta, disabled, className = '' }) {
  const [copiado, setCopiado] = useState(false)
  async function copiar() {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2000)
    } catch {
      /* sin permiso de portapapeles: el texto sigue visible para copiarlo a mano */
    }
  }
  return (
    <button
      onClick={copiar}
      disabled={disabled}
      aria-label={etiqueta || 'Copiar'}
      className={`inline-flex items-center justify-center gap-1.5 rounded-xl text-sm font-semibold py-2.5 px-4 disabled:opacity-50 ${className}`}
    >
      {copiado ? <Check size={16} /> : <Copy size={16} />}
      {etiqueta && (copiado ? 'Copiado' : etiqueta)}
    </button>
  )
}

function Lista({ pasos }) {
  return (
    <ol className="list-decimal pl-5 mt-2 space-y-2 text-sm text-ink-soft">
      {pasos.map((p, i) => <li key={i}>{p}</li>)}
    </ol>
  )
}

function Bloque({ titulo, children }) {
  return (
    <details className="rounded-xl border border-line p-3">
      <summary className="text-sm font-semibold text-ink cursor-pointer min-h-6">{titulo}</summary>
      {children}
    </details>
  )
}

export default function AtajoAvanzado({ claveAtajo }) {
  // El contenido no se pinta hasta abrir «Avanzado»: la clave no se repite en pantalla sin que se pida.
  const [abierto, setAbierto] = useState(false)
  const apiKey = claveAtajo.clave
  const scriptAndroid = apiKey ? SCRIPT_ANDROID(apiKey) : null

  function descargarScript() {
    if (!scriptAndroid) return
    const url = URL.createObjectURL(new Blob([scriptAndroid], { type: 'text/javascript' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'cuadrame_tasker.js'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <details
      className="mx-6 mt-6 rounded-2xl bg-paper-raised border border-line p-4"
      data-testid="avanzado"
      onToggle={(e) => setAbierto(e.currentTarget.open)}
    >
      <summary className="text-sm font-semibold cursor-pointer min-h-6">Avanzado</summary>
      <p className="text-xs text-ink-soft mt-2">
        Solo si el enlace del atajo no te funciona, usas Android o quieres registrar por voz.
      </p>
      {abierto && <div className="mt-3 space-y-3">
        <Bloque titulo="Armar el atajo a mano (si el enlace falla)">
          <ol className="list-decimal pl-5 mt-2 space-y-2 text-sm text-ink-soft">
            <li>
              Abre <b>Atajos</b> → pestaña «Atajos» → <b>+</b>. Nómbralo «CuadraMe Apple Pay».{' '}
              <a href="shortcuts://create-shortcut" className="text-accent font-semibold inline-flex items-center gap-0.5">
                Abrir Atajos <ExternalLink size={16} />
              </a>
            </li>
            <li>
              Añade la acción <b>Obtener contenido de URL</b>. Dirección:
              <span className="block break-all text-xs text-ink mt-1">{API_URL}</span>
              <BotonCopiar texto={API_URL} etiqueta="Copiar dirección" className="border border-line text-ink mt-1.5 py-1.5" />
            </li>
            <li>Toca «Mostrar más»: <b>Método</b> = POST, <b>Cuerpo de la solicitud</b> = JSON.</li>
            <li>
              Agrega estos campos y, en cada valor, toca la variable <b>Entrada de atajo</b> y elige la propiedad que
              corresponde (Comercio, Importe, Tarjeta o pase, Fecha; los nombres pueden variar según tu iOS):
              <pre className="mt-1.5 text-[11px] leading-relaxed whitespace-pre-wrap rounded-lg bg-paper p-2.5 border border-line text-ink">{JSON_DEL_ATAJO}</pre>
            </li>
            <li>
              En <b>Encabezados</b> agrega <b>X-Api-Key</b> = tu clave y <b>Content-Type</b> = application/json.
            </li>
            <li>
              Añade <b>Obtener valor del diccionario</b> → clave <b>mensaje</b>, y después <b>Mostrar notificación</b> con
              ese valor.
            </li>
          </ol>
        </Bloque>

        <Bloque titulo="Armar a mano el atajo de cierre de app">
          <p className="text-sm text-ink-soft mt-2">
            Lleva: un <b>Texto</b> con tu clave; <b>Elegir del menú</b> «¿Hiciste algún movimiento?» con Gasto / Ingreso
            / No (en «No» pon <b>Detener este atajo</b>; en «Gasto» un <b>Texto</b> «gasto» y en «Ingreso» un{' '}
            <b>Texto</b> «ingreso»); <b>Obtener contenido de URL</b> (método GET, dirección terminada en{' '}
            <b>/movimientos/cuentas-rapido</b>, encabezado X-Api-Key) y <b>Elegir de la lista</b>; dos{' '}
            <b>Solicitar entrada</b> (monto y nota); y un <b>Obtener contenido de URL</b> igual al de arriba con este
            cuerpo:
          </p>
          <pre className="mt-1.5 text-[11px] leading-relaxed whitespace-pre-wrap rounded-lg bg-paper p-2.5 border border-line text-ink">{JSON_CIERRE_APP}</pre>
        </Bloque>

        <Bloque titulo="Android (con la app Tasker)">
          <Lista pasos={PASOS_ANDROID} />
          <div className="rounded-xl bg-paper border border-line p-3 mt-3">
            <pre className="text-[11px] leading-relaxed overflow-x-auto whitespace-pre text-ink-soft max-h-64 overflow-y-auto">
              {scriptAndroid || (claveAtajo.cargando
                ? <span className="skeleton inline-block h-3.5 w-48 align-middle" role="status" aria-label="Preparando tu script" />
                : 'Tu clave guardada ya no se puede mostrar, así que el script no se puede armar. Crea una clave nueva aquí abajo y aparecerá listo para copiar.')}
            </pre>
          </div>
          {!scriptAndroid && !claveAtajo.cargando && (
            <div className="rounded-xl bg-paper border border-line p-3 mt-3">
              <ClaveAtajo {...claveAtajo} />
            </div>
          )}
          <div className="flex gap-2 mt-3">
            <BotonCopiar texto={scriptAndroid || ''} etiqueta="Copiar script" disabled={!scriptAndroid} className="flex-1 bg-accent text-paper-raised py-3 rounded-2xl" />
            <button
              onClick={descargarScript}
              disabled={!scriptAndroid}
              className="w-12 rounded-2xl border border-line flex items-center justify-center disabled:opacity-50"
              aria-label="Descargar script"
            >
              <Download size={16} className="text-ink-soft" />
            </button>
          </div>
          <p className="text-xs text-ink-soft mt-2">El script ya trae tu clave: no lo compartas con nadie.</p>
        </Bloque>

        <Bloque titulo="Registrar por voz con Siri">
          <Lista pasos={PASOS_VOZ} />
          <p className="text-xs text-ink-soft mt-3 mb-1.5 font-medium uppercase tracking-wide">Dirección</p>
          <div className="rounded-xl bg-paper border border-line p-3 flex items-center gap-2">
            <p className="text-xs flex-1 truncate">{API_URL_VOZ}</p>
            <BotonCopiar texto={API_URL_VOZ} etiqueta="" className="w-11 h-11 shrink-0 bg-paper-raised !p-0" />
          </div>
          <p className="text-xs text-ink-soft mt-3 mb-1.5 font-medium uppercase tracking-wide">Tu clave</p>
          <div className="rounded-xl bg-paper border border-line p-3">
            {apiKey ? (
              <div className="flex items-center gap-2">
                <p className="text-xs flex-1 truncate">{apiKey}</p>
                <BotonCopiar texto={apiKey} etiqueta="" className="w-11 h-11 shrink-0 bg-paper-raised !p-0" />
              </div>
            ) : (
              <p className="text-xs text-ink-soft">
                {claveAtajo.cargando ? 'Cargando tu clave…' : 'Tu clave está guardada de forma segura; la copiaste en el paso 1. Si la perdiste, crea una nueva allí.'}
              </p>
            )}
          </div>
        </Bloque>
      </div>}
    </details>
  )
}
