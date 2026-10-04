// ALTERNATIVA LEGADA: ya no es la vía recomendada. La app (Perfil → Conectar tu
// celular) guía ahora el disparador «Transacción» de Atajos de iOS, que entrega
// comercio y monto exactos sin Scriptable ni leer notificaciones.
//
// CuadraMe — registro automático de movimientos desde notificaciones bancarias.
// Se ejecuta desde un Atajo de iOS (acción "Ejecutar script" de Scriptable)
// disparado por una automatización personal "cuando llega una notificación
// de <tu banco>". El Atajo debe pasar el "Contenido de la notificación"
// como entrada al script (queda disponible aquí como args.shortcutParameter).
//
// Configura API_KEY con la que ves en la app: Perfil → Conectar dispositivos.
// CUENTA es opcional: nombre (o parte del nombre) de la cuenta en CuadraMe
// a la que quieres que se asignen estos movimientos (ej. "Nequi", "Bancolombia").
// Si lo dejas vacío, usa la primera cuenta del usuario.

const API_URL = "https://backend-production-aeab.up.railway.app/movimientos/rapido";
const API_KEY = "PEGA_AQUI_TU_API_KEY";
const CUENTA = ""; // ej: "Nequi"

async function avisar(titulo, cuerpo) {
  const n = new Notification();
  n.title = titulo;
  n.body = cuerpo;
  await n.schedule();
}

function extraerMonto(texto) {
  const match = texto.match(/\$?\s?([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)/);
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

// Notificaciones de Apple Pay suelen venir como:
// "Tarjeta •••• 1234: Pagaste $45.000 en RAPPI COLOMBIA"
// o "Wallet: Transaction of $45,000 at STARBUCKS"
function extraerComercioApplePay(texto) {
  const match = texto.match(/\b(?:en|at)\s+([A-Za-zÀ-ú0-9][^,\n.]{2,40})$/i);
  return match ? match[1].trim() : null;
}

function esNotificacionApplePay(texto) {
  return /apple pay|wallet|tarjeta\s*[•·*]{2,4}\s*\d/i.test(texto);
}

async function main() {
  const texto = String(args.shortcutParameter || "").trim();
  if (!texto) {
    await avisar("CuadraMe — error", "No llegó texto de notificación al script.");
    return;
  }

  const monto = extraerMonto(texto);
  if (!monto) {
    await avisar("CuadraMe — error", "No se pudo extraer un monto de:\n" + texto.slice(0, 100));
    return;
  }

  const tipo = detectarTipo(texto);
  const esApplePay = esNotificacionApplePay(texto);
  const comercio = esApplePay ? extraerComercioApplePay(texto) : null;
  const descripcion = comercio ? `${comercio} (Apple Pay)` : texto.slice(0, 150);

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
      await avisar("✅ Registrado en CuadraMe", `${tipo === "income" ? "Ingreso" : "Gasto"} de $${COP} · ${res.categoria}`);
    } else {
      await avisar("CuadraMe — error del backend", String(res.detail || "respuesta inesperada"));
    }
  } catch (e) {
    await avisar("CuadraMe — error de red", String(e));
  }
}

await main();
Script.complete();
