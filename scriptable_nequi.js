// Finanzas AI Pro — registro automático de movimientos Nequi
// Se ejecuta desde un Atajo de iOS (acción "Ejecutar script" de Scriptable)
// disparado por una automatización personal "cuando llega una notificación
// de Nequi". El Atajo debe pasar el "Contenido de la notificación" como
// entrada al script (queda disponible aquí como args.shortcutParameter).

const WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwHHt7rpQ7jtgyGZMwhG4Em5jsIn4-9nVD7uph6erRRrb1gRlEqksNHaDqZkBRB22xu/exec";
const API_KEY = "danielfinanzaspro2026parado";

// Notificación local en el iPhone — útil para ver qué pasó sin abrir Scriptable.
async function avisar(titulo, cuerpo) {
  const n = new Notification();
  n.title = titulo;
  n.body = cuerpo;
  await n.schedule();
}

async function main() {
  const texto = String(args.shortcutParameter || "").trim();

  if (!texto) {
    await avisar("Nequi Auto — error", "No llegó texto de notificación al script.");
    return;
  }

  // Monto: acepta $50.000 / $50,000 / $50.000,50 / 50000 (con o sin símbolo).
  const matchMonto = texto.match(/\$?\s?([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)/);
  if (!matchMonto) {
    await avisar("Nequi Auto — error", "No se pudo extraer un monto de:\n" + texto.slice(0, 100));
    return;
  }

  // Limpieza: quita separadores de miles, deja solo el separador decimal si lo hay.
  let montoStr = matchMonto[1];
  const partes = montoStr.split(/[.,]/);
  if (partes.length > 1 && partes[partes.length - 1].length <= 2 && partes.length > 2) {
    // Último grupo de 1-2 dígitos con más de un separador = decimales (ej: 50.000,50)
    montoStr = partes.slice(0, -1).join("") + "." + partes[partes.length - 1];
  } else {
    montoStr = montoStr.replace(/[.,]/g, "");
  }
  const monto = parseFloat(montoStr);

  if (!monto || monto <= 0) {
    await avisar("Nequi Auto — error", "Monto inválido tras parsear: " + montoStr);
    return;
  }

  // Nequi: "Recibiste" = ingreso; "Enviaste"/"Pagaste"/"Compraste"/"Retiraste" = gasto.
  const esIngreso = /recibiste|te enviaron|consignaron/i.test(texto);
  const tipo = esIngreso ? "ingreso" : "gasto";

  const payload = {
    action: "nueva_txn",
    monto: monto,
    tipo: tipo,
    descripcion: "Nequi (automático): " + texto.slice(0, 120),
    api_key: API_KEY
  };

  const req = new Request(WEBAPP_URL);
  req.method = "POST";
  req.headers = { "Content-Type": "application/json" };
  req.body = JSON.stringify(payload);

  try {
    const res = await req.loadJSON();
    if (res && res.ok !== false) {
      const COP = monto.toLocaleString("es-CO");
      await avisar("✅ Nequi registrado", `${tipo === "ingreso" ? "Ingreso" : "Gasto"} de $${COP}`);
    } else {
      await avisar("Nequi Auto — backend error", String((res && res.error) || "respuesta inesperada"));
    }
  } catch (e) {
    await avisar("Nequi Auto — error de red", String(e));
  }
}

await main();
Script.complete();
