import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Check, Copy, Download } from 'lucide-react'
import { api } from '../lib/api'

const API_URL = 'https://backend-production-aeab.up.railway.app/movimientos/rapido'
const API_URL_VOZ = 'https://backend-production-aeab.up.railway.app/movimientos/rapido-voz'

const SCRIPT_IOS = (apiKey) => `// CuadraMe — registro automático de movimientos desde notificaciones bancarias.
// Se ejecuta desde un Atajo de iOS (acción "Ejecutar script" de Scriptable)
// disparado por una automatización personal "cuando llega una notificación
// de <tu banco>". El Atajo debe pasar el "Contenido de la notificación"
// como entrada al script (queda disponible aquí como args.shortcutParameter).
//
// CUENTA es opcional: nombre (o parte del nombre) de la cuenta en CuadraMe
// a la que quieres que se asignen estos movimientos (ej. "Nequi", "Bancolombia").
// Si lo dejas vacío, usa la primera cuenta del usuario.

const API_URL = "${API_URL}";
const API_KEY = "${apiKey}";
const CUENTA = ""; // ej: "Nequi"

async function avisar(titulo, cuerpo) {
  const n = new Notification();
  n.title = titulo;
  n.body = cuerpo;
  await n.schedule();
}

function extraerMonto(texto) {
  const match = texto.match(/\\$?\\s?([\\d]{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{1,2})?)/);
  if (!match) return null;

  let montoStr = match[1];
  const partes = montoStr.split(/[.,]/);
  if (partes.length > 2 && partes[partes.length - 1].length <= 2) {
    montoStr = partes.slice(0, -1).join("") + "." + partes[partes.length - 1];
  } else {
    montoStr = montoStr.replace(/[.,]/g, "");
  }
  const monto = parseFloat(montoStr);
  return monto > 0 ? monto : null;
}

function detectarTipo(texto) {
  const esIngreso = /recibiste|te enviaron|consignaron|abono|deposito|dep[oó]sito/i.test(texto);
  return esIngreso ? "income" : "expense";
}

function extraerComercioApplePay(texto) {
  const match = texto.match(/\\b(?:en|at)\\s+([A-Za-zÀ-ú0-9][^,\\n.]{2,40})$/i);
  return match ? match[1].trim() : null;
}

function esNotificacionApplePay(texto) {
  return /apple pay|wallet|tarjeta\\s*[•·*]{2,4}\\s*\\d/i.test(texto);
}

async function main() {
  const texto = String(args.shortcutParameter || "").trim();
  if (!texto) {
    await avisar("CuadraMe — error", "No llegó texto de notificación al script.");
    return;
  }

  const monto = extraerMonto(texto);
  if (!monto) {
    await avisar("CuadraMe — error", "No se pudo extraer un monto de:\\n" + texto.slice(0, 100));
    return;
  }

  const tipo = detectarTipo(texto);
  const esApplePay = esNotificacionApplePay(texto);
  const comercio = esApplePay ? extraerComercioApplePay(texto) : null;
  const descripcion = comercio ? \`\${comercio} (Apple Pay)\` : texto.slice(0, 150);

  const payload = {
    monto,
    tipo,
    descripcion,
    cuenta: CUENTA || undefined,
    fuente: esApplePay ? "apple_pay" : "shortcut",
  };

  const req = new Request(API_URL);
  req.method = "POST";
  req.headers = { "Content-Type": "application/json", "X-Api-Key": API_KEY };
  req.body = JSON.stringify(payload);

  try {
    const res = await req.loadJSON();
    if (req.response.statusCode >= 200 && req.response.statusCode < 300) {
      const COP = monto.toLocaleString("es-CO");
      await avisar("✅ Registrado en CuadraMe", \`\${tipo === "income" ? "Ingreso" : "Gasto"} de $\${COP} · \${res.categoria}\`);
    } else {
      await avisar("CuadraMe — error del backend", String(res.detail || "respuesta inesperada"));
    }
  } catch (e) {
    await avisar("CuadraMe — error de red", String(e));
  }
}

await main();
Script.complete();
`

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

const PASOS_IOS = [
  'Descarga la app gratuita "Scriptable" desde el App Store.',
  'Abre Scriptable → toca "+" para crear un script nuevo.',
  'Pega el script de abajo (ya trae tu API key incluida) y guárdalo como "CuadraMe".',
  'Abre la app "Atajos" (Shortcuts) → pestaña Automatización → "+" → "Crear automatización personal".',
  'Elige "Notificación recibida" → selecciona la app de tu banco.',
  'Añade la acción "Ejecutar script" (Scriptable) → elige el script "CuadraMe" → activa "Pasar entrada: Contenido de la notificación".',
  'Desactiva "Preguntar antes de ejecutar" para que corra en segundo plano.',
]

const PASOS_ANDROID = [
  'Instala "Tasker" desde Google Play (de pago, ~$3 USD) y "AutoNotification" (plugin gratuito, opcional pero recomendado).',
  'Crea un Perfil nuevo → Contexto "Event" → "Notification" → filtra por la app de tu banco (o Google Pay).',
  'En la Tarea asociada, agrega la acción "JavaScriptlet" (categoría Code).',
  'Pega el script de abajo (ya trae tu API key incluida).',
  'Guarda el perfil y actívalo. Concede a Tasker el permiso de "Acceso a notificaciones" cuando te lo pida Android.',
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

export default function ConectarDispositivo() {
  const navigate = useNavigate()
  const [apiKey, setApiKey] = useState(null)
  const [plataforma, setPlataforma] = useState('ios')
  const [copiado, setCopiado] = useState(false)

  useEffect(() => {
    api.apiKey().then((r) => setApiKey(r.api_key)).catch(() => {})
  }, [])

  const script =
    plataforma === 'voz'
      ? apiKey
      : apiKey
      ? (plataforma === 'ios' ? SCRIPT_IOS(apiKey) : SCRIPT_ANDROID(apiKey))
      : null

  async function copiarScript() {
    if (!script) return
    const texto = plataforma === 'voz' ? API_URL_VOZ : script
    await navigator.clipboard.writeText(texto)
    setCopiado(true)
    setTimeout(() => setCopiado(false), 2000)
  }

  async function copiarApiKey() {
    if (!apiKey) return
    await navigator.clipboard.writeText(apiKey)
    setCopiado(true)
    setTimeout(() => setCopiado(false), 2000)
  }

  function descargarScript() {
    if (!script || plataforma === 'voz') return
    const blob = new Blob([script], { type: 'text/javascript' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = plataforma === 'ios' ? 'cuadrame_scriptable.js' : 'cuadrame_tasker.js'
    a.click()
    URL.revokeObjectURL(url)
  }

  const pasos = plataforma === 'ios' ? PASOS_IOS : plataforma === 'android' ? PASOS_ANDROID : PASOS_VOZ

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pt-14 pb-2 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="w-9 h-9 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Conectar mi celular</h1>
      </header>

      <p className="mx-6 mt-2 text-xs text-ink-soft">
        Registra tus gastos automáticamente cuando llega una notificación bancaria, de Apple/Google Pay,
        o solo con tu voz — sin abrir la app.
      </p>

      <div className="flex gap-2 mx-6 mt-4">
        {[
          { id: 'ios', label: 'iPhone' },
          { id: 'android', label: 'Android' },
          { id: 'voz', label: 'Por voz (Siri)' },
        ].map((p) => (
          <button
            key={p.id}
            onClick={() => setPlataforma(p.id)}
            className={`flex-1 rounded-2xl py-2.5 text-sm font-semibold border ${
              plataforma === p.id ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Pasos</h2>
        <ol className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
          {pasos.map((paso, i) => (
            <li key={i} className="flex items-start gap-3 px-4 py-3.5">
              <span className="w-6 h-6 rounded-full bg-accent-soft text-accent text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                {i + 1}
              </span>
              <p className="text-sm">{paso}</p>
            </li>
          ))}
        </ol>
      </section>

      {plataforma === 'voz' ? (
        <section className="mx-6 mt-6">
          <h2 className="text-[15px] font-semibold mb-3">Datos para el Atajo</h2>

          <p className="text-xs text-ink-soft mb-1.5 font-medium uppercase tracking-wide">URL</p>
          <div className="rounded-2xl bg-paper-raised border border-line p-3 flex items-center gap-2 mb-3">
            <p className="text-xs flex-1 truncate">{API_URL_VOZ}</p>
            <button
              onClick={copiarScript}
              className="w-8 h-8 shrink-0 rounded-xl bg-paper flex items-center justify-center"
              aria-label="Copiar URL"
            >
              {copiado ? <Check size={14} className="text-accent" /> : <Copy size={14} className="text-ink-soft" />}
            </button>
          </div>

          <p className="text-xs text-ink-soft mb-1.5 font-medium uppercase tracking-wide">Tu clave (X-Api-Key)</p>
          <div className="rounded-2xl bg-paper-raised border border-line p-3 flex items-center gap-2">
            <p className="text-xs flex-1 truncate">{apiKey || 'Cargando...'}</p>
            <button
              onClick={copiarApiKey}
              disabled={!apiKey}
              className="w-8 h-8 shrink-0 rounded-xl bg-paper flex items-center justify-center disabled:opacity-50"
              aria-label="Copiar clave"
            >
              {copiado ? <Check size={14} className="text-accent" /> : <Copy size={14} className="text-ink-soft" />}
            </button>
          </div>

          <p className="text-xs text-ink-soft mt-3">
            No necesitas Scriptable para este modo — todo se configura con acciones visuales
            dentro de la app "Atajos" de Apple.
          </p>
        </section>
      ) : (
        <section className="mx-6 mt-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[15px] font-semibold">
              Script {plataforma === 'ios' ? '(Scriptable)' : '(Tasker JavaScriptlet)'}
            </h2>
          </div>

          <div className="rounded-2xl bg-paper-raised border border-line p-3">
            <pre className="text-[10px] leading-relaxed overflow-x-auto whitespace-pre text-ink-soft max-h-64 overflow-y-auto">
              {script || 'Cargando tu clave personal...'}
            </pre>
          </div>

          <div className="flex gap-2 mt-3">
            <button
              onClick={copiarScript}
              disabled={!script}
              className="flex-1 flex items-center justify-center gap-1.5 bg-accent text-white font-semibold rounded-2xl py-3 text-sm disabled:opacity-50"
            >
              {copiado ? <Check size={15} /> : <Copy size={15} />}
              {copiado ? 'Copiado' : 'Copiar script'}
            </button>
            <button
              onClick={descargarScript}
              disabled={!script}
              className="w-12 rounded-2xl border border-line flex items-center justify-center disabled:opacity-50"
              aria-label="Descargar"
            >
              <Download size={16} className="text-ink-soft" />
            </button>
          </div>

          <p className="text-xs text-ink-soft mt-3">
            Este script ya tiene tu clave personal incluida — no la compartas con nadie. Si la regeneras
            desde Perfil, vuelve aquí para copiar la versión actualizada.
          </p>
        </section>
      )}
    </div>
  )
}
