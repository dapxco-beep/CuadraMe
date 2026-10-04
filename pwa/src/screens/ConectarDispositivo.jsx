import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Check, CheckCircle2, Copy, Download, ExternalLink, Send, ShieldCheck } from 'lucide-react'
import { api } from '../lib/api'

const API_URL = 'https://backend-production-aeab.up.railway.app/movimientos/rapido'
const API_URL_VOZ = 'https://backend-production-aeab.up.railway.app/movimientos/rapido-voz'

// Enlace de iCloud del Atajo ya armado ("Agregar atajo" en un toque). Mientras esté
// vacío se muestra "pronto" y las instrucciones para armarlo a mano con acciones nativas.
export const ATAJO_ICLOUD_URL = ''

const JSON_DEL_ATAJO = `{
  "comercio": "<Comercio de la transacción>",
  "monto": "<Importe de la transacción>",
  "tarjeta": "<Tarjeta o pase de la transacción>",
  "fecha": "<Fecha de la transacción>",
  "moneda": "COP"
}`

const SCRIPT_ANDROID = (apiKey) => `// CuadraMe — registro automático de movimientos desde notificaciones bancarias
// o de Google Pay, para Android vía Tasker.
//
// Tasker expone el texto de la notificación en %ntitle/%ntext; en el
// JavaScriptlet se leen como global('ntitle') / global('ntext').

var API_URL = "${API_URL}";
var API_KEY = "${apiKey}";
var CUENTA = ""; // ej: "Bancolombia" — vacío usa la primera cuenta del usuario

function extraerMonto(texto) {
  var match = texto.match(/\\$?\\s?([\\d]{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{1,2})?)/);
  if (!match) return null;
  var montoStr = match[1];
  var partes = montoStr.split(/[.,]/);
  if (partes.length > 2 && partes[partes.length - 1].length <= 2) {
    montoStr = partes.slice(0, -1).join("") + "." + partes[partes.length - 1];
  } else {
    montoStr = montoStr.replace(/[.,]/g, "");
  }
  var monto = parseFloat(montoStr);
  return monto > 0 ? monto : null;
}

function detectarTipo(texto) {
  return /recibiste|te enviaron|consignaron|abono|dep[oó]sito/i.test(texto) ? "income" : "expense";
}

function esGooglePay(texto, titulo) {
  return /google pay|g pay|wallet/i.test(texto + " " + titulo);
}

function extraerComercioGooglePay(texto) {
  var match = texto.match(/\\b(?:a|en|at)\\s+([A-Za-zÀ-ú0-9][^,\\n.]{2,40})\\s+(?:con|with)\\s+google\\s*pay/i);
  return match ? match[1].trim() : null;
}

var titulo = global("ntitle") || "";
var cuerpo = global("ntext") || "";
var texto = (titulo + " " + cuerpo).trim();

if (!texto) {
  flash("CuadraMe: no llegó texto de notificación");
} else {
  var monto = extraerMonto(texto);
  if (!monto) {
    flash("CuadraMe: no se pudo extraer un monto");
  } else {
    var tipo = detectarTipo(texto);
    var googlePay = esGooglePay(texto, titulo);
    var comercio = googlePay ? extraerComercioGooglePay(texto) : null;
    var descripcion = comercio ? (comercio + " (Google Pay)") : texto.substring(0, 150);

    var payload = JSON.stringify({
      monto: monto,
      tipo: tipo,
      descripcion: descripcion,
      cuenta: CUENTA || undefined,
      fuente: googlePay ? "google_pay" : "shortcut",
    });

    var http = new XMLHttpRequest();
    http.open("POST", API_URL, false);
    http.setRequestHeader("Content-Type", "application/json");
    http.setRequestHeader("X-Api-Key", API_KEY);
    try {
      http.send(payload);
      if (http.status >= 200 && http.status < 300) {
        flash("✅ CuadraMe: " + (tipo === "income" ? "ingreso" : "gasto") + " de $" + monto.toLocaleString("es-CO"));
      } else {
        flash("CuadraMe: error del backend (" + http.status + ")");
      }
    } catch (e) {
      flash("CuadraMe: error de red — " + e);
    }
  }
}
`

const PASOS_ANDROID = [
  'Instala "Tasker" desde Google Play (de pago, ~$3 USD) y "AutoNotification" (plugin gratuito, opcional pero recomendado).',
  'Crea un Perfil nuevo → Contexto "Event" → "Notification" → filtra por la app de tu banco (o Google Pay).',
  'En la Tarea asociada, agrega la acción "JavaScriptlet" (categoría Code).',
  'Pega el script de abajo (ya trae tu clave incluida).',
  'Guarda el perfil y actívalo. Concede a Tasker el permiso de "Acceso a notificaciones" cuando te lo pida Android.',
  'Prueba con el botón de abajo: debe aparecer un movimiento "por confirmar" en CuadraMe.',
]

const PASOS_VOZ = [
  'Abre la app "Atajos" (Shortcuts) en tu iPhone → pestaña "Mis Atajos" → toca "+".',
  'Toca "Añadir acción" → busca "Dictado de texto" → agrégala (así hablas y se convierte en texto).',
  'Busca la acción "Obtener contenido de URL" y agrégala después. Configúrala: URL = la de abajo, Método = POST.',
  'En "Cuerpo de solicitud" elige JSON y agrega dos campos: "texto" con el valor del Dictado de texto (el resultado del paso 2), y "cuenta" (opcional, vacío).',
  'Añade el encabezado (Header) "X-Api-Key" con tu clave de abajo, y "Content-Type" con valor "application/json".',
  'Agrega al final la acción "Mostrar notificación" mostrando el resultado, para saber si CuadraMe entendió bien.',
  'Nombra el Atajo "Registrar gasto" y actívalo para Siri (⋯ → Añadir a Siri, di una frase como "Oye Siri, registrar gasto").',
  'Ahora puedes decir: "Oye Siri, registrar gasto" y luego "gasté 20 mil en el almuerzo" — se registra solo.',
]

/* ---------- "Capturas" dibujadas con SVG (livianas, con los colores de la marca) ---------- */

function Pantalla({ children, titulo }) {
  return (
    <svg viewBox="0 0 220 120" className="w-full h-auto" role="img" aria-label={titulo}>
      <rect x="1" y="1" width="218" height="118" rx="14" className="fill-paper stroke-line" strokeWidth="2" />
      {children}
    </svg>
  )
}

function Fila({ y, ancho = 120, resaltada = false, etiqueta }) {
  return (
    <g>
      <rect x="14" y={y} width="192" height="22" rx="8" className={resaltada ? 'fill-accent-soft stroke-accent' : 'fill-paper-raised stroke-line'} strokeWidth="1.5" />
      <rect x="22" y={y + 8} width={ancho} height="6" rx="3" className={resaltada ? 'fill-accent' : 'fill-line'} />
      {etiqueta && (
        <text x="198" y={y + 15} textAnchor="end" fontSize="8" className="fill-ink-soft">{etiqueta}</text>
      )}
    </g>
  )
}

function CapturaClave() {
  return (
    <Pantalla titulo="Dibujo: copiar tu clave desde CuadraMe">
      <text x="14" y="22" fontSize="10" fontWeight="700" className="fill-ink">Tu clave</text>
      <rect x="14" y="32" width="146" height="24" rx="8" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <text x="22" y="48" fontSize="9" className="fill-ink-soft">cm_••••••••••••••••</text>
      <rect x="166" y="32" width="40" height="24" rx="8" className="fill-accent" />
      <text x="186" y="48" fontSize="9" textAnchor="middle" fontWeight="700" className="fill-paper-raised">Copiar</text>
      <text x="14" y="82" fontSize="8" className="fill-ink-soft">Es como tu contraseña para el Atajo.</text>
      <text x="14" y="94" fontSize="8" className="fill-ink-soft">No la compartas con nadie.</text>
    </Pantalla>
  )
}

function CapturaAtajo() {
  return (
    <Pantalla titulo="Dibujo: el Atajo con la acción Obtener contenido de URL">
      <text x="14" y="20" fontSize="10" fontWeight="700" className="fill-ink">CuadraMe Wallet</text>
      <Fila y={28} ancho={110} resaltada etiqueta="Obtener contenido de URL" />
      <Fila y={54} ancho={90} etiqueta="POST · JSON" />
      <Fila y={80} ancho={100} etiqueta="X-Api-Key" />
    </Pantalla>
  )
}

function CapturaAutomatizacion() {
  return (
    <Pantalla titulo="Dibujo: Automatización personal con el disparador Transacción">
      <text x="14" y="20" fontSize="10" fontWeight="700" className="fill-ink">Nueva automatización</text>
      <Fila y={28} ancho={70} resaltada etiqueta="Transacción" />
      <Fila y={54} ancho={90} etiqueta="Tus tarjetas" />
      <Fila y={80} ancho={110} etiqueta="Ejecutar inmediatamente" />
    </Pantalla>
  )
}

function Paso({ n, titulo, children, dibujo }) {
  return (
    <li className="px-4 py-4">
      <div className="flex items-start gap-3">
        <span className="w-6 h-6 rounded-full bg-accent-soft text-accent text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
          {n}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold">{titulo}</p>
          <div className="text-sm text-ink-soft mt-1 space-y-2">{children}</div>
          {dibujo && <div className="mt-3 max-w-[260px]">{dibujo}</div>}
        </div>
      </div>
    </li>
  )
}

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
      {copiado ? <Check size={15} /> : <Copy size={15} />}
      {etiqueta && (copiado ? 'Copiado' : etiqueta)}
    </button>
  )
}

/* ---------- Prueba de punta a punta ---------- */

function PruebaConexion({ apiKey }) {
  const [estado, setEstado] = useState('inicial') // inicial | enviando | ok | error
  const [mensaje, setMensaje] = useState('')

  async function probar() {
    setEstado('enviando')
    setMensaje('')
    try {
      const r = await api.pagoDePrueba(apiKey)
      // Verifica que de verdad llegó a la bandeja "por confirmar".
      const lista = await api.movimientosPorConfirmar()
      if (!lista.some((m) => m.id === r.id)) throw new Error('El pago se envió pero no apareció por confirmar. Intenta de nuevo.')
      setMensaje(r.mensaje || 'Llegó tu pago de prueba.')
      setEstado('ok')
      window.dispatchEvent(new CustomEvent('cuadrame:movimientos-cambio'))
    } catch (err) {
      setMensaje(err.status === 401 ? 'Tu clave no es válida. Revisa o regénerala en Perfil.' : err.message || 'No se pudo enviar la prueba')
      setEstado('error')
    }
  }

  return (
    <section className="mx-6 mt-6" aria-label="Prueba de conexión">
      <h2 className="text-[15px] font-semibold mb-3">Prueba</h2>
      <div className="rounded-2xl bg-paper-raised border border-line p-4">
        <p className="text-sm text-ink-soft">
          Enviamos un pago de $1.000 «de prueba» como si viniera de tu celular, para comprobar que todo llega.
          Aparecerá en la bandeja «¿son tuyos?»; puedes descartarlo.
        </p>
        <button
          onClick={probar}
          disabled={!apiKey || estado === 'enviando'}
          className="w-full mt-3 flex items-center justify-center gap-2 bg-accent text-white font-semibold rounded-2xl py-3 text-sm disabled:opacity-50"
        >
          <Send size={15} /> {estado === 'enviando' ? 'Enviando...' : 'Enviar un pago de prueba'}
        </button>
        {estado === 'ok' && (
          <div role="status" className="mt-3 rounded-xl bg-cuadra-soft px-3.5 py-3 flex items-start gap-2.5">
            <CheckCircle2 size={18} className="text-cuadra shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-bold">¡Funciona!</p>
              <p className="text-xs text-ink-soft mt-0.5">{mensaje}</p>
            </div>
          </div>
        )}
        {estado === 'error' && (
          <p role="alert" className="text-sm text-danger mt-3">{mensaje}</p>
        )}
      </div>
    </section>
  )
}

function AvisoPrivacidad() {
  return (
    <section className="mx-6 mt-6 rounded-2xl bg-paper-raised border border-line p-4 flex items-start gap-3" aria-label="Privacidad">
      <ShieldCheck size={18} className="text-accent shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-semibold">Qué datos viajan</p>
        <p className="text-xs text-ink-soft mt-1 leading-relaxed">
          Solo el comercio, el monto, el nombre de la tarjeta, la fecha y la moneda de cada pago, junto con tu clave
          personal. Nunca el número completo de tu tarjeta, tu clave del banco ni tus otras apps. Todo viaja por
          conexión segura (HTTPS) a tu cuenta de CuadraMe, y puedes cortar la conexión cuando quieras regenerando la
          clave en Perfil.
        </p>
      </div>
    </section>
  )
}

export default function ConectarDispositivo() {
  const navigate = useNavigate()
  const [apiKey, setApiKey] = useState(null)
  const [plataforma, setPlataforma] = useState('ios')

  useEffect(() => {
    api.apiKey().then((r) => setApiKey(r.api_key)).catch(() => {})
  }, [])

  const scriptAndroid = apiKey ? SCRIPT_ANDROID(apiKey) : null

  function descargarScript() {
    if (!scriptAndroid) return
    const blob = new Blob([scriptAndroid], { type: 'text/javascript' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'cuadrame_tasker.js'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pt-14 pb-2 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="w-9 h-9 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Conectar tu celular</h1>
      </header>

      <p className="mx-6 mt-2 text-xs text-ink-soft">
        Cada vez que pagues con tu celular, CuadraMe lo registra solo y al abrir la app te pregunta si fue tuyo.
        Toma unos 2 minutos y es gratis.
      </p>

      <div className="flex gap-2 mx-6 mt-4" role="tablist" aria-label="Tu celular">
        {[
          { id: 'ios', label: 'iPhone' },
          { id: 'android', label: 'Android' },
          { id: 'voz', label: 'Por voz (Siri)' },
        ].map((p) => (
          <button
            key={p.id}
            role="tab"
            aria-selected={plataforma === p.id}
            onClick={() => setPlataforma(p.id)}
            className={`flex-1 rounded-2xl py-2.5 text-sm font-semibold border ${
              plataforma === p.id ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {plataforma === 'ios' && (
        <>
          <section className="mx-6 mt-6" aria-label="Guía para iPhone">
            <h2 className="text-[15px] font-semibold mb-3">Guía de 2 minutos</h2>
            <ol className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
              <Paso n={1} titulo="Copia tu clave" dibujo={<CapturaClave />}>
                <p>Es la llave que le dice al Atajo que los pagos son tuyos.</p>
                <BotonCopiar texto={apiKey || ''} etiqueta="Copiar mi clave" disabled={!apiKey} className="bg-accent text-white" />
              </Paso>

              <Paso n={2} titulo="Agrega el Atajo" dibujo={<CapturaAtajo />}>
                {ATAJO_ICLOUD_URL ? (
                  <a
                    href={ATAJO_ICLOUD_URL}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-accent text-white text-sm font-semibold py-2.5 px-4"
                  >
                    <Download size={15} /> Agregar el Atajo
                  </a>
                ) : (
                  <p className="rounded-xl bg-accent-soft text-accent text-xs font-semibold px-3 py-2 inline-block">
                    El Atajo de un toque llega pronto. Mientras tanto, créalo en 1 minuto así:
                  </p>
                )}
                <details className="rounded-xl border border-line p-3" open={!ATAJO_ICLOUD_URL}>
                  <summary className="text-sm font-semibold text-ink cursor-pointer">Armar el Atajo a mano</summary>
                  <ol className="list-decimal pl-5 mt-2 space-y-2 text-sm">
                    <li>
                      Abre <b>Atajos</b> → pestaña «Atajos» → <b>+</b>. Nómbralo «CuadraMe Wallet».{' '}
                      <a href="shortcuts://create-shortcut" className="text-accent font-semibold inline-flex items-center gap-0.5">
                        Abrir Atajos <ExternalLink size={12} />
                      </a>
                    </li>
                    <li>
                      Añade la acción <b>Obtener contenido de URL</b>. URL:
                      <span className="block break-all text-xs text-ink mt-1">{API_URL}</span>
                      <BotonCopiar texto={API_URL} etiqueta="Copiar URL" className="border border-line text-ink mt-1.5 py-1.5" />
                    </li>
                    <li>Toca «Mostrar más»: <b>Método</b> = POST, <b>Cuerpo de la solicitud</b> = JSON.</li>
                    <li>
                      Agrega estos campos de texto y, en cada valor, toca la variable <b>Entrada de atajo</b> y elige la
                      propiedad que corresponde (Comercio, Importe, Tarjeta o pase, Fecha; los nombres pueden variar un
                      poco según tu iOS):
                      <pre className="mt-1.5 text-[10px] leading-relaxed whitespace-pre-wrap rounded-lg bg-paper p-2.5 border border-line text-ink">{JSON_DEL_ATAJO}</pre>
                    </li>
                    <li>
                      En <b>Encabezados</b> agrega <b>X-Api-Key</b> = tu clave (la del paso 1) y{' '}
                      <b>Content-Type</b> = application/json.
                    </li>
                    <li>
                      Añade <b>Obtener valor del diccionario</b> → clave <b>mensaje</b>, y después{' '}
                      <b>Mostrar notificación</b> con ese valor: verás «Gasto de $18.500 en Juan Valdez…» al pagar.
                    </li>
                  </ol>
                </details>
              </Paso>

              <Paso n={3} titulo="Crea la automatización" dibujo={<CapturaAutomatizacion />}>
                <p>
                  En <b>Atajos → Automatización → +</b> elige <b>Transacción</b>, selecciona tus tarjetas de Wallet,
                  marca <b>Ejecutar inmediatamente</b> y como acción elige el Atajo «CuadraMe Wallet».
                </p>
                <a href="shortcuts://" className="text-accent font-semibold text-sm inline-flex items-center gap-1">
                  Abrir Atajos <ExternalLink size={13} />
                </a>
                <p className="text-xs">
                  Tip: si tu tarjeta de Wallet se llama distinto a tu cuenta, ponle un «alias de tarjeta» a la cuenta
                  (Perfil → Ver y editar mis cuentas) y los pagos caerán en la cuenta correcta.
                </p>
              </Paso>

              <Paso n={4} titulo="Haz la prueba">
                <p>Baja a «Prueba» y toca «Enviar un pago de prueba». Si ves «¡Funciona!», ya estás listo.</p>
              </Paso>
            </ol>
          </section>
          <PruebaConexion apiKey={apiKey} />
        </>
      )}

      {plataforma === 'android' && (
        <>
          <section className="mx-6 mt-6" aria-label="Guía para Android">
            <h2 className="text-[15px] font-semibold mb-3">Pasos (Tasker)</h2>
            <ol className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
              {PASOS_ANDROID.map((paso, i) => (
                <li key={i} className="flex items-start gap-3 px-4 py-3.5">
                  <span className="w-6 h-6 rounded-full bg-accent-soft text-accent text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-sm">{paso}</p>
                </li>
              ))}
            </ol>
          </section>

          <section className="mx-6 mt-6">
            <h2 className="text-[15px] font-semibold mb-3">Script (Tasker JavaScriptlet)</h2>
            <div className="rounded-2xl bg-paper-raised border border-line p-3">
              <pre className="text-[10px] leading-relaxed overflow-x-auto whitespace-pre text-ink-soft max-h-64 overflow-y-auto">
                {scriptAndroid || 'Cargando tu clave personal...'}
              </pre>
            </div>
            <div className="flex gap-2 mt-3">
              <BotonCopiar texto={scriptAndroid || ''} etiqueta="Copiar script" disabled={!scriptAndroid} className="flex-1 bg-accent text-white py-3 rounded-2xl" />
              <button
                onClick={descargarScript}
                disabled={!scriptAndroid}
                className="w-12 rounded-2xl border border-line flex items-center justify-center disabled:opacity-50"
                aria-label="Descargar"
              >
                <Download size={16} className="text-ink-soft" />
              </button>
            </div>
            <p className="text-xs text-ink-soft mt-3">
              Este script ya tiene tu clave personal incluida: no la compartas con nadie. Si la regeneras desde
              Perfil, vuelve aquí para copiar la versión actualizada.
            </p>
          </section>
          <PruebaConexion apiKey={apiKey} />
        </>
      )}

      {plataforma === 'voz' && (
        <>
          <section className="mx-6 mt-6">
            <h2 className="text-[15px] font-semibold mb-3">Pasos</h2>
            <ol className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
              {PASOS_VOZ.map((paso, i) => (
                <li key={i} className="flex items-start gap-3 px-4 py-3.5">
                  <span className="w-6 h-6 rounded-full bg-accent-soft text-accent text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-sm">{paso}</p>
                </li>
              ))}
            </ol>
          </section>

          <section className="mx-6 mt-6">
            <h2 className="text-[15px] font-semibold mb-3">Datos para el Atajo</h2>
            <p className="text-xs text-ink-soft mb-1.5 font-medium uppercase tracking-wide">URL</p>
            <div className="rounded-2xl bg-paper-raised border border-line p-3 flex items-center gap-2 mb-3">
              <p className="text-xs flex-1 truncate">{API_URL_VOZ}</p>
              <BotonCopiar texto={API_URL_VOZ} etiqueta="" className="w-8 h-8 shrink-0 bg-paper !p-0" />
            </div>
            <p className="text-xs text-ink-soft mb-1.5 font-medium uppercase tracking-wide">Tu clave (X-Api-Key)</p>
            <div className="rounded-2xl bg-paper-raised border border-line p-3 flex items-center gap-2">
              <p className="text-xs flex-1 truncate">{apiKey || 'Cargando...'}</p>
              <BotonCopiar texto={apiKey || ''} etiqueta="" disabled={!apiKey} className="w-8 h-8 shrink-0 bg-paper !p-0" />
            </div>
            <p className="text-xs text-ink-soft mt-3">
              Todo se configura con acciones visuales dentro de la app «Atajos» de Apple, sin instalar nada más.
            </p>
          </section>
        </>
      )}

      <AvisoPrivacidad />

      {plataforma === 'ios' && (
        <p className="mx-6 mt-4 text-[11px] text-ink-soft">
          ¿Usabas Scriptable? Sigue funcionando, pero ya no hace falta: el disparador «Transacción» de Atajos
          entrega el comercio y el monto exactos, sin leer notificaciones.
        </p>
      )}
    </div>
  )
}
