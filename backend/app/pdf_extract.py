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
OPENROUTER_MODEL = "nvidia/nemotron-nano-12b-v2-vl:free"


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


def extraer_via_ia(texto_plano: str, cuenta: str, banco: str) -> list[dict]:
    """Manda el texto del extracto a OpenRouter por trozos y parsea la respuesta JSON."""
    api_key = settings.openrouter_api_key
    if not api_key or not texto_plano:
        return []

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
                    "model": OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 4096,
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
