"""
Extracción de texto de extractos bancarios en PDF, y fallback vía IA
(OpenRouter) cuando los parsers regex no reconocen el formato del banco.
Reemplaza el flujo de Google Drive OCR de PdfReconciliation.js.
"""
import base64
import io
import json
import re

import httpx
import pdfplumber

from app.config import settings
from app.contabilidad import tipo_con_direccion

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Modelo gratuito: sus proveedores pueden guardar y entrenar con lo que reciben. Por eso SOLO
# se usa con texto que el usuario subió él mismo, ya enmascarado y con su consentimiento «ia».
OPENROUTER_MODEL = "nvidia/nemotron-nano-12b-v2-vl:free"

# Origen del contenido. «gmail» = viene de Google (Uso Limitado: no se transfiere a terceros
# ni se usa para IA generalizada); «manual» = el usuario lo subió desde su dispositivo.
ORIGEN_GMAIL = "gmail"
ORIGEN_MANUAL = "manual"


def modelo_ia_permitido(origen: str, consentimiento_ia: bool) -> str | None:
    """Modelo de OpenRouter que se puede usar para este contenido, o None = NO llamar a la IA.

    - Sin consentimiento «ia» vigente: nunca.
    - Gmail: solo con modelo PRIVADO (de pago, sin entrenamiento) definido en
      OPENROUTER_MODEL_PRIVADO; sin esa variable, nunca (por defecto está vacía).
    - Manual: el privado si existe; si no, el gratuito (texto enmascarado).
    Cualquier origen desconocido se trata como Gmail (lo más restrictivo)."""
    if not consentimiento_ia or not settings.openrouter_api_key:
        return None
    privado = (settings.openrouter_model_privado or "").strip()
    if origen == ORIGEN_MANUAL:
        return privado or OPENROUTER_MODEL
    return privado or None


# ── Minimización: lo que sale hacia la IA va sin datos de identificación ──────────
_RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_RE_LINEA_CLAVE = re.compile(r"(?i)\b(clave|contrase[ñn]a|password|passw\w*|pin|token|cvv|cvc|otp)\b")
_RE_DOCUMENTO = re.compile(
    r"(?i)\b(c\.?\s?c\.?|c[eé]dula(?:\s+de\s+ciudadan[ií]a)?|nit|documento|identificaci[oó]n|ce)\b"
    r"(\s*(?:n[oº°.]*|numero|número|#|:)?\s*)\d[\d.\-\s]{4,14}\d"
)
_RE_TELEFONO = re.compile(r"(?<![\d.,])(?:\+?57[\s-]?)?3\d{2}[\s-]?\d{3}[\s-]?\d{4}(?![\d.,])")
_RE_TARJETA = re.compile(r"(?<![\d.,])\d{4}(?:[ -]\d{4}){2,4}(?![\d.,])")
_RE_NUMERO_LARGO = re.compile(r"(?<![\d.,])\d{9,}(?![\d.,])")
_RE_ENMASCARADA = re.compile(r"[*xX•]{2,}\s?\d{2,4}")


def enmascarar_texto(texto: str, nombre_titular: str = "") -> str:
    """Quita del texto lo que identifica a la persona antes de enviarlo a un proveedor de IA:
    líneas con claves/PIN, correos, teléfonos, cédula/NIT, números largos (cuentas, tarjetas)
    y el nombre del titular. Los montos (con separadores) y las fechas se conservan."""
    if not texto:
        return ""
    lineas = [l for l in texto.split("\n") if not _RE_LINEA_CLAVE.search(l)]
    t = "\n".join(lineas)
    t = _RE_CORREO.sub("[correo]", t)
    t = _RE_DOCUMENTO.sub(lambda m: f"{m.group(1)}{m.group(2)}[documento]", t)
    t = _RE_TELEFONO.sub("[telefono]", t)
    t = _RE_ENMASCARADA.sub("[cuenta]", t)
    t = _RE_TARJETA.sub("[cuenta]", t)
    t = _RE_NUMERO_LARGO.sub("[cuenta]", t)
    nombre = " ".join((nombre_titular or "").split())
    if len(nombre) >= 3:
        for parte in {nombre, *[p for p in nombre.split() if len(p) >= 4]}:
            t = re.sub(re.escape(parte), "[titular]", t, flags=re.IGNORECASE)
    return t


# Un extracto real tiene pocas páginas. Sin tope, un PDF de miles de páginas dejaría
# el servidor (compartido por todos los clientes) procesando minutos para un solo usuario.
MAX_PAGINAS_EXTRACTO = 60


def _decodificar_pdf(pdf_base64: str) -> bytes | None:
    """Bytes del PDF, o None si el base64 está roto o lo decodificado no es un PDF
    (el archivo debe empezar por %PDF-; así no se le entregan a pdfplumber cosas raras)."""
    try:
        datos = base64.b64decode(pdf_base64.split(",", 1)[-1])
    except (ValueError, TypeError):
        return None
    return datos if datos[:1024].lstrip().startswith(b"%PDF-") else None


def pdf_a_texto(pdf_base64: str, password: str = "") -> str:
    pdf_bytes = _decodificar_pdf(pdf_base64)
    if pdf_bytes is None:
        return ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes), password=password or None) as pdf:
            paginas = [pagina.extract_text() or "" for pagina in pdf.pages[:MAX_PAGINAS_EXTRACTO]]
        return "\n".join(paginas)
    except Exception:
        return ""


def pdf_pide_clave(pdf_base64: str, password: str = "") -> bool:
    """True si el PDF no se pudo abrir por estar protegido (falta la clave o es incorrecta)."""
    pdf_bytes = _decodificar_pdf(pdf_base64)
    if pdf_bytes is None:
        return False
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes), password=password or None):
            return False
    except Exception as e:  # pdfminer envuelve PDFPasswordIncorrect
        return "password" in repr(e).lower()


def _build_prompt_extraccion(cuenta: str, banco: str) -> str:
    banco_hint = f"Banco/entidad: {banco.capitalize()}. " if banco not in ("generico", "desconocido") else ""
    return "\n".join([
        "Eres un extractor de datos bancarios colombianos. Lee este extracto y extrae TODOS los movimientos.",
        f"Cuenta bancaria: {cuenta}. {banco_hint}",
        "IMPORTANTE: Extrae CADA movimiento sin excepción. El extracto está en español (Colombia).",
        "",
        "Devuelve SOLO este JSON válido (sin markdown, sin texto extra):",
        '{"movimientos":[',
        '  {"fecha":"YYYY-MM-DD","descripcion":"texto exacto del banco","monto":123456.78,"tipo":"expense|income","referencia":"123456"}',
        "]}",
        "",
        "Reglas:",
        '- Débitos, cargos, pagos, compras => "expense"',
        '- Créditos, abonos, consignaciones, depósitos => "income"',
        '- Transferencias y traslados: "expense" si el dinero SALE de la cuenta (Para…, Enviaste…), "income" si ENTRA (De…, Recibiste…). Nunca uses "transfer"',
        "- monto siempre positivo",
        "- fecha formato YYYY-MM-DD obligatorio",
        "- Si el monto tiene puntos de miles (ej: 1.234.567), conviértelo a 1234567",
        "- NO incluyas totales, subtotales ni encabezados",
    ])


def extraer_via_ia(
    texto_plano: str, cuenta: str, banco: str, *,
    origen: str, consentimiento_ia: bool = False, nombre_titular: str = "",
) -> list[dict]:
    """Manda el texto del extracto (ENMASCARADO) a OpenRouter por trozos y parsea el JSON.
    `origen` es obligatorio: con contenido de Gmail no hay llamada de red salvo que existan
    consentimiento «ia» y un modelo privado (ver `modelo_ia_permitido`)."""
    api_key = settings.openrouter_api_key
    modelo = modelo_ia_permitido(origen, consentimiento_ia)
    if not api_key or not texto_plano or not modelo:
        return []
    privado = modelo != OPENROUTER_MODEL
    texto_plano = enmascarar_texto(texto_plano, nombre_titular)

    lineas = [l.strip() for l in texto_plano.split("\n") if l.strip()]
    relevantes = [
        l for l in lineas
        if re.search(r"\d{1,2}\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)", l, re.IGNORECASE)
        or re.search(r"[$]|\d[\d.,]{2,}", l)
    ]
    fuente = relevantes if len(relevantes) >= 3 else lineas

    prompt_base = _build_prompt_extraccion(cuenta, banco)
    todos: list[dict] = []
    tam = 25

    for i in range(0, min(len(fuente), tam * 6), tam):
        trozo = "\n".join(fuente[i:i + tam])
        if not trozo.strip():
            continue
        prompt = f"{prompt_base}\n\nTEXTO DEL EXTRACTO (parte):\n{trozo}"
        try:
            resp = httpx.post(
                OPENROUTER_URL,
                json={
                    "model": modelo,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 4096,
                    # Con el modelo privado se exige además que el proveedor no guarde ni entrene.
                    **({"provider": {"data_collection": "deny"}} if privado else {}),
                },
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=60,
            )
        except httpx.HTTPError:
            continue

        if resp.status_code == 429:
            break
        if resp.status_code != 200:
            continue

        try:
            data = resp.json()
            texto_resp = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError):
            continue

        movs = _parse_respuesta_ia(texto_resp)
        todos.extend(movs)

    return todos


def _parse_respuesta_ia(texto: str) -> list[dict]:
    texto = re.sub(r"```json\s*|```\s*", "", texto).strip()
    try:
        parsed = json.loads(texto)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*"movimientos"[\s\S]*\}', texto)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    movimientos = parsed.get("movimientos", [])
    resultado = []
    for m in movimientos:
        try:
            monto = abs(float(m.get("monto", 0)))
        except (TypeError, ValueError):
            continue
        fecha = m.get("fecha")
        if not fecha or monto <= 0:
            continue
        resultado.append({
            "fecha": fecha,
            "descripcion": str(m.get("descripcion", "")).strip(),
            "monto": monto,
            "tipo": tipo_con_direccion(str(m.get("tipo", "expense")).lower(), str(m.get("descripcion", ""))) or "expense",
            "referencia": str(m.get("referencia", "")).strip(),
            "saldo": None,
        })
    return resultado
