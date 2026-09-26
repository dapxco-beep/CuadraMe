// Finanzas AI Pro — registro manual rápido
// iOS no permite leer el contenido de una notificación de otra app (Nequi,
// Nu, etc.) desde una Automatización — es una restricción de privacidad del
// propio sistema, no algo evitable. La alternativa práctica: disparar este
// script cuando CIERRAS la app (Atajos sí soporta "App > Es cerrada"), justo
// después de hacer la transferencia, mientras el monto lo tienes fresco.
//
// Formas de lanzarlo:
//  (a) Automatización "Nequi es cerrada" → Ejecutar script, pasando el texto
//      "Nequi" como entrada → abre el formulario con esa app prellenada.
//  (b) Atajo con Siri, diciendo algo como "50000 almuerzo" → lo interpreta solo
//      y registra directo, sin mostrar el formulario.
//  (c) Tocado directo desde Scriptable, sin nada de entrada → abre el formulario en blanco.

const WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwHHt7rpQ7jtgyGZMwhG4Em5jsIn4-9nVD7uph6erRRrb1gRlEqksNHaDqZkBRB22xu/exec";
const API_KEY = "danielfinanzaspro2026parado";

const CATEGORIAS = ["Alimentos", "Transporte", "Servicios", "Salud", "Entretenimiento", "Hogar", "Otros"];

async function avisar(titulo, cuerpo) {
  const n = new Notification();
  n.title = titulo;
  n.body = cuerpo;
  await n.schedule();
}

// Intenta interpretar frases tipo "50000 almuerzo" o "gasté 50 mil en almuerzo"
// dichas por Siri. Si no reconoce nada útil, se abre el formulario visual.
function parseTextoLibre(texto) {
  if (!texto) return null;
  const matchMonto = texto.match(/(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(mil|k)?/i);
  if (!matchMonto) return null;

  let monto = parseFloat(matchMonto[1].replace(/[.,]/g, ""));
  if (/mil|k/i.test(matchMonto[2] || "")) monto *= 1000;
  if (!monto || monto <= 0) return null;

  const descripcion = texto.replace(matchMonto[0], "").trim() || "Gasto rápido";
  const esIngreso = /recib[íi]|ingreso|me pagaron|cobr[ée]/i.test(texto);

  return { monto, descripcion, tipo: esIngreso ? "ingreso" : "gasto" };
}

function construirHTML(origen) {
  const chips = CATEGORIAS.map(c => `<div class="chip" data-cat="${c}" onclick="elegirCat('${c}')">${c}</div>`).join("");
  const tituloApp = origen ? origen : "Registro rápido";

  return `
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body {
    margin: 0; padding: 20px 18px 28px;
    background: #0b0f14; color: #e5e9ee;
    font-family: -apple-system, system-ui, sans-serif;
    display: flex; flex-direction: column; min-height: 100vh;
  }
  .titulo { font-size: 14px; font-weight: 600; color: #9aa4b2; text-align: center; margin-bottom: 4px; }
  .subtitulo { font-size: 12px; color: #5a6472; text-align: center; margin-bottom: 18px; }

  .monto-wrap { display: flex; align-items: center; justify-content: center; margin: 8px 0 22px; }
  .monto-signo { font-size: 32px; color: #5a6472; margin-right: 4px; font-weight: 300; }
  #monto {
    font-size: 48px; font-weight: 700; background: none; border: none; color: #e5e9ee;
    width: 100%; text-align: center; outline: none; font-variant-numeric: tabular-nums;
  }
  #monto::placeholder { color: #2a323d; }

  .toggle { display: flex; background: #141a22; border-radius: 12px; padding: 4px; margin-bottom: 18px; }
  .toggle-btn {
    flex: 1 1 0; min-width: 0; text-align: center; padding: 11px 4px; border-radius: 9px;
    font-size: 14px; font-weight: 600; color: #9aa4b2; transition: all .15s;
  }
  .toggle-btn.active.gasto { background: #ef4444; color: #fff; }
  .toggle-btn.active.ingreso { background: #10b981; color: #fff; }

  .label { font-size: 12px; font-weight: 600; color: #9aa4b2; margin: 4px 0 8px; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
  .chip {
    padding: 9px 14px; border-radius: 999px; background: #141a22; border: 1px solid #2a323d;
    font-size: 13px; color: #9aa4b2; font-weight: 500;
  }
  .chip.active { background: #3b82f6; border-color: #3b82f6; color: #fff; }

  #descripcion {
    width: 100%; padding: 13px; border-radius: 10px; border: 1px solid #2a323d;
    background: #141a22; color: #e5e9ee; font-size: 14px; margin-bottom: 22px;
  }
  #descripcion::placeholder { color: #5a6472; }

  .spacer { flex: 1; max-height: 60px; }
  #guardar {
    width: 100%; padding: 16px; border: none; border-radius: 14px;
    background: #3b82f6; color: #fff; font-weight: 700; font-size: 16px;
  }
  #guardar:active { opacity: .8; }
  #cancelar {
    width: 100%; padding: 12px; border: none; background: none;
    color: #5a6472; font-size: 13px; margin-top: 10px;
  }
  #exito {
    display: none; flex: 1; flex-direction: column; align-items: center; justify-content: center;
    text-align: center;
  }
  #exito .check {
    width: 64px; height: 64px; border-radius: 50%; background: #10b981;
    display: flex; align-items: center; justify-content: center; font-size: 32px; margin-bottom: 16px;
  }
  #exito .msg { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
  #exito .hint { font-size: 12px; color: #5a6472; }
</style>
</head>
<body>
  <div id="form" style="display:flex; flex-direction:column; flex:1;">
    <div class="titulo">${tituloApp}</div>
    <div class="subtitulo">Finanzas AI Pro</div>

    <div class="monto-wrap">
      <span class="monto-signo">$</span>
      <input id="monto" type="tel" inputmode="numeric" placeholder="0" autofocus>
    </div>

    <div class="toggle">
      <div class="toggle-btn active gasto" id="btnGasto" onclick="elegirTipo('gasto')">Gasto</div>
      <div class="toggle-btn ingreso" id="btnIngreso" onclick="elegirTipo('ingreso')">Ingreso</div>
    </div>

    <div class="label">Categoría</div>
    <div class="chips" id="chips">${chips}</div>

    <input id="descripcion" type="text" placeholder="Descripción (opcional)" value="${origen || ""}">

    <div class="spacer"></div>
    <button id="guardar" onclick="guardar()">Guardar</button>
    <button id="cancelar" onclick="completion(null)">Cancelar</button>
  </div>

  <div id="exito">
    <div class="check">✓</div>
    <div class="msg" id="exitoMsg">Registrado</div>
    <div class="hint">Desliza hacia abajo para cerrar</div>
  </div>

<script>
  let tipo = "gasto";
  let categoria = "";

  function elegirTipo(t) {
    tipo = t;
    document.getElementById("btnGasto").classList.toggle("active", t === "gasto");
    document.getElementById("btnIngreso").classList.toggle("active", t === "ingreso");
  }

  function elegirCat(c) {
    categoria = (categoria === c) ? "" : c;
    document.querySelectorAll(".chip").forEach(el => {
      el.classList.toggle("active", el.dataset.cat === categoria);
    });
  }

  function guardar() {
    const monto = parseFloat(document.getElementById("monto").value);
    if (!monto || monto <= 0) {
      document.getElementById("monto").style.color = "#ef4444";
      return;
    }
    const COP = monto.toLocaleString("es-CO");
    document.getElementById("exitoMsg").textContent =
      (tipo === "ingreso" ? "Ingreso" : "Gasto") + " de $" + COP;
    document.getElementById("form").style.display = "none";
    document.getElementById("exito").style.display = "flex";

    completion({
      monto: monto,
      tipo: tipo,
      categoria: categoria,
      descripcion: document.getElementById("descripcion").value
    });
  }

  document.getElementById("monto").addEventListener("input", (e) => {
    e.target.style.color = "#e5e9ee";
  });
</script>
</body>
</html>`;
}

// present() sólo se resuelve cuando el usuario CIERRA la vista (swipe down),
// no cuando toca "Guardar" — no hay forma de cerrar el WebView por código.
// Si el usuario cierra deslizando sin guardar, evaluateJavaScript("completion")
// se queda esperando para siempre porque completion() nunca se llamó. Por eso
// se corre en carrera contra la propia present(): la que termine primero gana.
async function pedirPorPantalla(origen) {
  const wv = new WebView();
  await wv.loadHTML(construirHTML(origen || ""));

  const cerrado = wv.present(false).then(() => null); // swipe down sin guardar
  const guardado = wv.evaluateJavaScript("completion", true);   // tocó Guardar

  return await Promise.race([guardado, cerrado]);
}

async function main() {
  // Cuando el Atajo se dispara al cerrar Nequi/Nu, se le puede pasar el
  // nombre de la app como entrada (texto simple, ej: "Nequi") en vez de
  // una frase de Siri — en ese caso se usa como app prellenada en el título.
  const entrada = String(args.shortcutParameter || "").trim();
  const appsConocidas = ["nequi", "nu", "daviplata"];
  const esNombreApp = appsConocidas.includes(entrada.toLowerCase());

  let datos = !esNombreApp && entrada ? parseTextoLibre(entrada) : null;

  if (!datos) {
    datos = await pedirPorPantalla(esNombreApp ? entrada : "");
  }
  if (!datos) return; // usuario canceló

  const payload = {
    action: "nueva_txn",
    monto: datos.monto,
    tipo: datos.tipo,
    categoria: datos.categoria || undefined,
    descripcion: datos.descripcion || (datos.tipo === "ingreso" ? "Ingreso rápido" : "Gasto rápido"),
    api_key: API_KEY
  };

  const req = new Request(WEBAPP_URL);
  req.method = "POST";
  req.headers = { "Content-Type": "application/json" };
  req.body = JSON.stringify(payload);

  try {
    const res = await req.loadJSON();
    if (res && res.ok !== false) {
      const COP = datos.monto.toLocaleString("es-CO");
      await avisar("✅ Registrado", `${datos.tipo === "ingreso" ? "Ingreso" : "Gasto"} de $${COP} — ${payload.descripcion}`);
    } else {
      await avisar("Error del backend", String((res && res.error) || "respuesta inesperada"));
    }
  } catch (e) {
    await avisar("Error de red", String(e));
  }
}

await main();
Script.complete();
