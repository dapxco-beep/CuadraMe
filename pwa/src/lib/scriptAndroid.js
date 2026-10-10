// Textos largos de la sección «Avanzado» del registro automático (Android con Tasker, Siri, armado a mano).
// Viven aquí para que la pantalla principal quede corta y sin jerga. Sin React.
export const API_URL = 'https://backend-production-aeab.up.railway.app/movimientos/rapido'
export const API_URL_VOZ = 'https://backend-production-aeab.up.railway.app/movimientos/rapido-voz'

export const JSON_DEL_ATAJO = `{
  "comercio": "<Comercio de la transacción>",
  "monto": "<Importe de la transacción>",
  "tarjeta": "<Tarjeta o pase de la transacción>",
  "fecha": "<Fecha de la transacción>",
  "moneda": "COP"
}`

export const JSON_CIERRE_APP = `{
  "tipo": "<Resultado del menú: gasto o ingreso>",
  "monto": "<variable monto>",
  "descripcion": "<variable nota (puede ir vacía)>",
  "cuenta": "<Elemento elegido: la cuenta que tocaste en la lista>",
  "fuente": "cierre_app"
}`

export const SCRIPT_ANDROID = (apiKey) => `// CuadraMe — registro automático de movimientos desde notificaciones bancarias
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

export const PASOS_ANDROID = [
  'Instala "Tasker" desde Google Play (de pago, ~$3 USD) y "AutoNotification" (plugin gratuito, opcional pero recomendado).',
  'Crea un Perfil nuevo → Contexto "Event" → "Notification" → filtra por la app de tu banco (o Google Pay).',
  'En la Tarea asociada, agrega la acción "JavaScriptlet" (categoría Code).',
  'Pega el script de abajo (ya trae tu clave incluida).',
  'Guarda el perfil y actívalo. Concede a Tasker el permiso de "Acceso a notificaciones" cuando te lo pida Android.',
  'Prueba con el botón de abajo: debe aparecer un movimiento "por confirmar" en CuadraMe.',
]

export const PASOS_VOZ = [
  'Abre la app "Atajos" (Shortcuts) en tu iPhone → pestaña "Mis Atajos" → toca "+".',
  'Toca "Añadir acción" → busca "Dictado de texto" → agrégala (así hablas y se convierte en texto).',
  'Busca la acción "Obtener contenido de URL" y agrégala después. Configúrala: URL = la de abajo, Método = POST.',
  'En "Cuerpo de solicitud" elige JSON y agrega dos campos: "texto" con el valor del Dictado de texto (el resultado del paso 2), y "cuenta" (opcional, vacío).',
  'Añade el encabezado (Header) "X-Api-Key" con tu clave de abajo, y "Content-Type" con valor "application/json".',
  'Agrega al final la acción "Mostrar notificación" mostrando el resultado, para saber si CuadraMe entendió bien.',
  'Nombra el Atajo "Registrar gasto" y actívalo para Siri (⋯ → Añadir a Siri, di una frase como "Oye Siri, registrar gasto").',
  'Ahora puedes decir: "Oye Siri, registrar gasto" y luego "gasté 20 mil en el almuerzo" — se registra solo.',
]

