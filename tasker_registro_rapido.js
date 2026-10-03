// CuadraMe — registro automático de movimientos desde notificaciones bancarias
// o de Google Pay, para Android vía Tasker.
//
// CÓMO CONFIGURARLO EN TASKER:
// 1. Crea un Perfil nuevo → Contexto "Notification" → filtra por la app de tu
//    banco (o "Google Pay" / com.google.android.apps.walletnfcrel).
// 2. En la Tarea asociada, agrega una acción "JavaScriptlet" (Code) y pega
//    el contenido de este archivo (reemplaza API_KEY abajo).
//    Tasker expone el texto de la notificación en la variable %ntitle/%ntext;
//    en el JavaScriptlet se leen como global('ntitle') / global('ntext').
// 3. Agrega después una acción "HTTP Request" (POST) — o deja que este mismo
//    JavaScriptlet haga el POST con XMLHttpRequest (Tasker lo soporta).

var API_URL = "https://backend-production-aeab.up.railway.app/movimientos/rapido";
var API_KEY = "PEGA_AQUI_TU_API_KEY";
var CUENTA = ""; // ej: "Bancolombia" — vacío usa la primera cuenta del usuario

function extraerMonto(texto) {
  var match = texto.match(/\$?\s?([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)/);
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
  // Notificaciones típicas: "Pagaste $45.000 a RAPPI COLOMBIA con Google Pay"
  var match = texto.match(/\b(?:a|en|at)\s+([A-Za-zÀ-ú0-9][^,\n.]{2,40})\s+(?:con|with)\s+google\s*pay/i);
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
    http.open("POST", API_URL, false); // síncrono: Tasker espera el resultado
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
