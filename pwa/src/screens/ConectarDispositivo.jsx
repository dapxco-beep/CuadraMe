import { useState } from 'react'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Check, CheckCircle2, Copy, Download, ExternalLink, Send, ShieldCheck } from 'lucide-react'
import { api } from '../lib/api'
import ClaveAtajo from '../components/ClaveAtajo'
import { useClaveAtajo } from '../lib/useClaveAtajo'

const API_URL = 'https://backend-production-aeab.up.railway.app/movimientos/rapido'
const API_URL_VOZ = 'https://backend-production-aeab.up.railway.app/movimientos/rapido-voz'

// Enlaces de iCloud de los dos atajos ya armados: el cliente NO construye nada, solo los instala
// y, cuando iOS le pregunta «Pega tu clave de Cuádrame», pega la clave del paso 1.
//  - Pagos con Apple Pay (la automatización «Transacción» le entrega comercio, monto y tarjeta).
//  - Cierre de la app del banco (pregunta «¿Hiciste algún movimiento?»).
// Si un enlace cambia, quien ya instaló el atajo conserva su versión: hay que pegar el nuevo aquí.
export const ATAJO_ICLOUD_URL = 'https://www.icloud.com/shortcuts/8b2de178aff84465a938df4a5ef9c0dc'
export const ATAJO_CIERRE_URL = 'https://www.icloud.com/shortcuts/d34fa153ac844631baf36d8e158f7bf4'

const JSON_DEL_ATAJO = `{
  "comercio": "<Comercio de la transacción>",
  "monto": "<Importe de la transacción>",
  "tarjeta": "<Tarjeta o pase de la transacción>",
  "fecha": "<Fecha de la transacción>",
  "moneda": "COP"
}`

const JSON_CIERRE_APP = `{
  "tipo": "<Resultado del menú: gasto o ingreso>",
  "monto": "<variable monto>",
  "descripcion": "<variable nota (puede ir vacía)>",
  "cuenta": "<Elemento elegido: la cuenta que tocaste en la lista>",
  "fuente": "cierre_app"
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
      <text x="14" y="20" fontSize="10" fontWeight="700" className="fill-ink">CuadraMe Apple Pay</text>
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

// Lo que verá la persona al instalar un atajo: iOS pregunta por la clave y ella la pega.
function CapturaPegarClave({ titulo = 'CuadraMe Apple Pay' }) {
  return (
    <Pantalla titulo={`Dibujo: al instalar ${titulo}, iOS pregunta «Pega tu clave de Cuádrame»; mantén presionado y elige Pegar`}>
      <text x="14" y="20" fontSize="10" fontWeight="700" className="fill-ink">{titulo}</text>
      <text x="14" y="38" fontSize="8" className="fill-ink-soft">Pega tu clave de Cuádrame</text>
      <rect x="14" y="44" width="192" height="24" rx="8" className="fill-paper-raised stroke-accent" strokeWidth="1.5" />
      <text x="22" y="60" fontSize="9" className="fill-ink">cdm_a1b2c3…</text>
      <rect x="120" y="72" width="54" height="20" rx="8" className="fill-ink" />
      <text x="147" y="85" fontSize="8" fontWeight="700" textAnchor="middle" className="fill-paper">Pegar</text>
      <rect x="14" y="96" width="192" height="16" rx="8" className="fill-accent" />
      <text x="110" y="107" fontSize="8" fontWeight="700" textAnchor="middle" className="fill-paper-raised">Agregar atajo</text>
    </Pantalla>
  )
}

function CapturaCierreApp() {
  return (
    <Pantalla titulo="Dibujo: automatización personal con el disparador App, marcando Se cierra">
      <text x="14" y="20" fontSize="10" fontWeight="700" className="fill-ink">Nueva automatización</text>
      <Fila y={28} ancho={60} resaltada etiqueta="App" />
      <Fila y={54} ancho={90} etiqueta="Se cierra" />
      <Fila y={80} ancho={110} etiqueta="Ejecutar atajo" />
    </Pantalla>
  )
}

function Flecha({ x1, y1, x2, y2 }) {
  return <line x1={x1} y1={y1} x2={x2} y2={y2} className="stroke-accent" strokeWidth="2" markerEnd="url(#punta)" />
}

function DiagramaAtajo() {
  return (
    <svg viewBox="0 0 320 170" className="w-full h-auto" role="img" aria-label="Diagrama: Apple Pay y el cierre de cualquier app registran en CuadraMe, cada uno con su Atajo">
      <defs>
        <marker id="punta" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" className="fill-accent" />
        </marker>
      </defs>
      <rect x="4" y="14" width="104" height="48" rx="10" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <text x="56" y="34" fontSize="10" fontWeight="700" textAnchor="middle" className="fill-ink">Apple Pay</text>
      <text x="56" y="49" fontSize="8" textAnchor="middle" className="fill-ink-soft">Transacción</text>
      <rect x="4" y="108" width="104" height="48" rx="10" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <text x="56" y="128" fontSize="10" fontWeight="700" textAnchor="middle" className="fill-ink">Cierre de una app</text>
      <text x="56" y="143" fontSize="8" textAnchor="middle" className="fill-ink-soft">App → Se cierra</text>
      <Flecha x1="108" y1="38" x2="136" y2="70" />
      <Flecha x1="108" y1="132" x2="136" y2="100" />
      <rect x="138" y="52" width="92" height="66" rx="12" className="fill-accent-soft stroke-accent" strokeWidth="1.5" />
      <text x="184" y="74" fontSize="10" fontWeight="700" textAnchor="middle" className="fill-ink">Atajo</text>
      <text x="184" y="87" fontSize="10" fontWeight="700" textAnchor="middle" className="fill-ink">CuadraMe</text>
      <text x="184" y="102" fontSize="7" textAnchor="middle" className="fill-ink-soft">con datos: registra</text>
      <text x="184" y="112" fontSize="7" textAnchor="middle" className="fill-ink-soft">sin datos: pregunta</text>
      <Flecha x1="230" y1="85" x2="252" y2="85" />
      <rect x="254" y="60" width="62" height="50" rx="10" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <text x="285" y="82" fontSize="9" fontWeight="700" textAnchor="middle" className="fill-ink">CuadraMe</text>
      <text x="285" y="96" fontSize="7" textAnchor="middle" className="fill-ink-soft">por confirmar</text>
    </svg>
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
      {copiado ? <Check size={16} /> : <Copy size={16} />}
      {etiqueta && (copiado ? 'Copiado' : etiqueta)}
    </button>
  )
}

/* ---------- Prueba de punta a punta ---------- */

function PruebaConexion({ apiKey, conRegistroRapido = false }) {
  return (
    <section className="mx-6 mt-6" aria-label="Prueba de conexión">
      <h2 className="text-[15px] font-semibold mb-3">Pruebas</h2>
      <div className="space-y-3">
        <BloquePrueba
          apiKey={apiKey}
          enviar={api.pagoDePrueba}
          texto="Enviamos un pago de $1.000 «de prueba» como si viniera de Apple Pay, para comprobar que todo llega. Aparecerá en la bandeja «¿son tuyos?»; puedes descartarlo."
          boton="Enviar un pago de prueba"
          exito="¡Funciona!"
        />
        {conRegistroRapido && (
          <BloquePrueba
            apiKey={apiKey}
            enviar={api.registroRapidoDePrueba}
            texto="Crea un movimiento de $1.000 «de prueba» como si hubieras cerrado la app de tu banco y respondido que sí hiciste un movimiento. Queda por confirmar; puedes descartarlo."
            boton="Probar registro rápido"
            exito="¡Funciona el registro rápido!"
          />
        )}
      </div>
    </section>
  )
}

function BloquePrueba({ apiKey, enviar, texto, boton, exito }) {
  const [estado, setEstado] = useState('inicial') // inicial | enviando | ok | error
  const [mensaje, setMensaje] = useState('')

  async function probar() {
    setEstado('enviando')
    setMensaje('')
    try {
      const r = await enviar(apiKey)
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
      <div className="rounded-2xl bg-paper-raised border border-line p-4">
        <p className="text-sm text-ink-soft">{texto}</p>
        <button
          onClick={probar}
          disabled={estado === 'enviando'}
          className="w-full mt-3 flex items-center justify-center gap-2 bg-accent text-white font-semibold rounded-2xl py-3 text-sm disabled:opacity-50"
        >
          <Send size={16} /> {estado === 'enviando' ? 'Enviando...' : boton}
        </button>
        {estado === 'ok' && (
          <div role="status" className="mt-3 rounded-xl bg-cuadra-soft px-3.5 py-3 flex items-start gap-2.5">
            <CheckCircle2 size={20} className="text-cuadra shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-bold">{exito}</p>
              <p className="text-xs text-ink-soft mt-0.5">{mensaje}</p>
            </div>
          </div>
        )}
        {estado === 'error' && (
          <p role="alert" className="text-sm text-danger mt-3">{mensaje}</p>
        )}
      </div>
  )
}

function AvisoPrivacidad() {
  return (
    <section className="mx-6 mt-6 rounded-2xl bg-paper-raised border border-line p-4 flex items-start gap-3" aria-label="Privacidad">
      <ShieldCheck size={20} className="text-accent shrink-0 mt-0.5" />
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
  const volver = useVolver('/perfil')
  const claveAtajo = useClaveAtajo()
  const apiKey = claveAtajo.clave // null si la clave guardada ya no se puede leer (solo existe su hash)
  const [plataforma, setPlataforma] = useState('ios')

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
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
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
          <section className="mx-6 mt-6" aria-label="Dos atajos, dos tipos de automatización">
            <h2 className="text-[15px] font-semibold mb-3">Dos atajos, dos tipos de automatización</h2>
            <div className="rounded-2xl bg-paper-raised border border-line p-4">
              <DiagramaAtajo />
              <ul className="mt-3 space-y-2 text-sm text-ink-soft list-disc pl-5">
                <li>
                  <span className="font-semibold text-ink">Pagos con Apple Pay:</span> iOS le entrega al Atajo el comercio, el
                  monto y la tarjeta; el Atajo los manda solo, sin preguntarte nada.
                </li>
                <li>
                  <span className="font-semibold text-ink">Cierre de la app de tu banco:</span> el Atajo no recibe datos, así
                  que te pregunta «¿Hiciste algún movimiento?». Si dices que sí, escribes el monto y una nota opcional.
                </li>
              </ul>
              <p className="text-xs text-ink-soft mt-3">
                Después, cuando subas tu extracto, CuadraMe empareja cada movimiento con el del banco y lo completa con el
                nombre real del comercio o de quien te pagó.
              </p>
            </div>
          </section>

          <section className="mx-6 mt-6" aria-label="Guía para iPhone">
            <h2 className="text-[15px] font-semibold mb-3">Tres pasos, sin armar nada</h2>
            <ol className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
              <Paso n={1} titulo="Crea tu clave y cópiala" dibujo={<CapturaClave />}>
                <p>Es la llave que le dice al atajo que los pagos son tuyos. Tócala para copiarla: la vas a pegar en el paso 2 y en el 3.</p>
                <div className="mt-2"><ClaveAtajo {...claveAtajo} /></div>
              </Paso>

              <Paso n={2} titulo="Instala el atajo de pagos" dibujo={<CapturaPegarClave />}>
                <p>
                  Toca el botón. Se abre la app <b>Atajos</b> y te pregunta <b>«Pega tu clave de Cuádrame»</b>: mantén
                  presionado, elige <b>Pegar</b> y toca <b>Agregar atajo</b>.
                </p>
                <a
                  href={ATAJO_ICLOUD_URL}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-accent text-white text-sm font-semibold py-2.5 px-4 min-h-11"
                >
                  <Download size={16} /> Instalar atajo de pagos
                </a>
              </Paso>

              <Paso n={3} titulo="Instala el atajo de cierre y activa las automatizaciones" dibujo={<CapturaPegarClave titulo="CuadraMe Cierre" />}>
                <p>
                  Igual que antes: toca el botón, pega la misma clave cuando la pida y toca <b>Agregar atajo</b>.
                </p>
                <a
                  href={ATAJO_CIERRE_URL}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-accent text-white text-sm font-semibold py-2.5 px-4 min-h-11"
                >
                  <Download size={16} /> Instalar atajo de cierre
                </a>
                <p>
                  Falta que el celular los ejecute solo. En <b>Atajos → Automatización → +</b> crea estas dos
                  (una vez y listo):
                </p>
              </Paso>
            </ol>

            <div className="mt-3 rounded-2xl bg-paper-raised border border-line p-4 space-y-5" data-testid="automatizaciones">
              <div>
                <h3 className="text-sm font-semibold" id="auto-pagos">Automatización 1: pagos con Apple Pay</h3>
                <div className="mt-2 max-w-[260px]"><CapturaAutomatizacion /></div>
                <ol className="list-decimal pl-5 mt-2 space-y-1 text-sm text-ink-soft" aria-labelledby="auto-pagos">
                  <li>Toca <b>Transacción</b> (cuando recibas un pago de Wallet) y elige tus tarjetas.</li>
                  <li>Toca <b>Siguiente</b> → <b>Ejecutar atajo</b> → «CuadraMe Apple Pay».</li>
                  <li>Marca <b>Ejecutar inmediatamente</b>.</li>
                </ol>
                <p className="text-xs text-ink-soft mt-2">
                  Tip: si tu tarjeta de Wallet se llama distinto a tu cuenta, ponle un «alias de tarjeta» a la cuenta
                  (Perfil → Ver y editar mis cuentas) y los pagos caerán en la cuenta correcta.
                </p>
              </div>
              <div>
                <h3 className="text-sm font-semibold" id="auto-cierre">Automatización 2: cierre de una app (una por app)</h3>
                <div className="mt-2 max-w-[260px]"><CapturaCierreApp /></div>
                <ol className="list-decimal pl-5 mt-2 space-y-1 text-sm text-ink-soft" aria-labelledby="auto-cierre">
                  <li>Toca <b>App</b>, elige la app de tu banco (Nequi, Daviplata…) y marca <b>Se cierra</b> (desmarca «Se abre»).</li>
                  <li>Toca <b>Siguiente</b> → <b>Ejecutar atajo</b> → «CuadraMe Cierre».</li>
                  <li>Marca <b>Ejecutar inmediatamente</b>. Repite por cada app que quieras vigilar.</li>
                </ol>
                <p className="text-xs text-ink-soft mt-2">
                  Al cerrar esa app el celular pregunta «¿Hiciste algún movimiento?». Si no, toca «No».
                </p>
              </div>
              <a href="shortcuts://" className="text-accent font-semibold text-sm inline-flex items-center gap-1 min-h-11">
                Abrir Atajos <ExternalLink size={16} />
              </a>
            </div>

            <div className="mt-3 rounded-2xl bg-paper-raised border border-line p-4 space-y-3">
              <h3 className="text-sm font-semibold">Qué verás</h3>
              <p className="text-sm text-ink-soft">
                <span className="font-semibold text-ink">Al pagar con Apple Pay:</span> una notificación «Gasto de $18.500
                en Juan Valdez…» y el movimiento queda «por confirmar» en CuadraMe.
              </p>
              <p className="text-sm text-ink-soft">
                <span className="font-semibold text-ink">Al cerrar tu banco:</span> el celular pregunta «¿Hiciste algún
                movimiento?». Con «Gasto» o «Ingreso» te pide el monto y una nota opcional; con «No» no pasa nada.
              </p>
              <p className="text-sm text-ink-soft">
                <span className="font-semibold text-ink">Al subir tu extracto:</span> los movimientos se completan con los
                datos del banco y los que no aparecen te los mostramos aparte.
              </p>
              <p className="text-sm text-ink-soft">
                Para comprobar que todo quedó bien, baja a «Pruebas» y toca «Enviar un pago de prueba».
              </p>
            </div>

            <details className="rounded-xl border border-line p-3">
              <summary className="text-sm font-semibold text-ink cursor-pointer">Avanzado: armar los atajos a mano (si el enlace falla)</summary>
              <ol className="list-decimal pl-5 mt-2 space-y-2 text-sm">
                <li>
                  Abre <b>Atajos</b> → pestaña «Atajos» → <b>+</b>. Nómbralo «CuadraMe Apple Pay».{' '}
                  <a href="shortcuts://create-shortcut" className="text-accent font-semibold inline-flex items-center gap-0.5">
                    Abrir Atajos <ExternalLink size={16} />
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
                  <pre className="mt-1.5 text-[11px] leading-relaxed whitespace-pre-wrap rounded-lg bg-paper p-2.5 border border-line text-ink">{JSON_DEL_ATAJO}</pre>
                </li>
                <li>
                  En <b>Encabezados</b> agrega <b>X-Api-Key</b> = tu clave (la del paso 1) y{' '}
                  <b>Content-Type</b> = application/json.
                </li>
                <li>
                  Añade <b>Obtener valor del diccionario</b> → clave <b>mensaje</b>, y después{' '}
                  <b>Mostrar notificación</b> con ese valor: verás «Gasto de $18.500 en Juan Valdez…» al pagar.
                </li>
                <li>
                  Para el cierre de una app crea un <b>segundo Atajo</b>, «CuadraMe Cierre», más corto: acción{' '}
                  <b>Texto</b> con tu clave; <b>Elegir del menú</b> «¿Hiciste algún movimiento?» con Gasto / Ingreso /
                  No (en «No» pon <b>Detener este atajo</b>; en «Gasto» pon un <b>Texto</b> «gasto» y en «Ingreso» un <b>Texto</b> «ingreso»: no las dejes vacías); <b>Solicitar entrada</b>{' '}
                  (número) «¿Cuánto fue?» y <b>Establecer variable</b> <b>monto</b>; antes de eso, una acción <b>Obtener contenido de URL</b> (método GET, dirección terminada en <b>/movimientos/cuentas-rapido</b>, encabezado X-Api-Key) y <b>Elegir de la lista</b> «¿En qué cuenta?» para escoger tu cuenta; <b>Solicitar entrada</b> (texto)
                  «¿En qué?» y <b>Establecer variable</b> <b>nota</b>. Luego <b>Obtener contenido de URL</b> igual que
                  arriba, con este cuerpo, y por último <b>Obtener valor del diccionario</b> (mensaje) y{' '}
                  <b>Mostrar notificación</b>:
                  <pre className="mt-1.5 text-[11px] leading-relaxed whitespace-pre-wrap rounded-lg bg-paper p-2.5 border border-line text-ink">{JSON_CIERRE_APP}</pre>
                  Si dejas la nota vacía, se guarda como «Movimiento en» y el nombre de la cuenta.
                </li>
              </ol>
            </details>
          </section>
          <PruebaConexion apiKey={apiKey} conRegistroRapido />
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
              <pre className="text-[11px] leading-relaxed overflow-x-auto whitespace-pre text-ink-soft max-h-64 overflow-y-auto">
                {scriptAndroid || (claveAtajo.cargando
                  ? <span className="skeleton inline-block h-3.5 w-48 align-middle" role="status" aria-label="Preparando tu script" />
                  : 'Tu clave guardada ya no se puede mostrar, así que el script no se puede armar. Crea una clave nueva aquí abajo y aparecerá listo para copiar.')}
              </pre>
            </div>
            {!scriptAndroid && !claveAtajo.cargando && (
              <div className="rounded-2xl bg-paper-raised border border-line p-3 mt-3">
                <ClaveAtajo {...claveAtajo} />
              </div>
            )}
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
              <BotonCopiar texto={API_URL_VOZ} etiqueta="" className="w-11 h-11 shrink-0 bg-paper !p-0" />
            </div>
            <p className="text-xs text-ink-soft mb-1.5 font-medium uppercase tracking-wide">Tu clave (X-Api-Key)</p>
            <div className="rounded-2xl bg-paper-raised border border-line p-3">
              {apiKey ? (
                <div className="flex items-center gap-2">
                  <p className="text-xs flex-1 truncate">{apiKey}</p>
                  <BotonCopiar texto={apiKey} etiqueta="" className="w-11 h-11 shrink-0 bg-paper !p-0" />
                </div>
              ) : (
                <p className="text-xs text-ink-soft">
                  {claveAtajo.cargando ? 'Cargando tu clave…' : 'Tu clave está guardada de forma segura; la copiaste en el paso 1. Si la perdiste, crea una nueva allí.'}
                </p>
              )}
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
