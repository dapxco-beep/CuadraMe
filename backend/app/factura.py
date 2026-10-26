"""
Lectura de facturas/recibos con un modelo de visión vía OpenRouter.

Privacidad: la imagen solo vive en memoria durante la petición. Nunca se guarda
en disco ni en la base de datos, y este módulo no la escribe en ningún log
(tampoco el cuerpo de la respuesta del modelo: solo el resultado ya parseado).
"""
import base64
import json
import re
from datetime import date, datetime

import httpx

from app.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Mismo modelo gratuito (con visión) que ya usan insights.py y pdf_extract.py.
# Necesita visión: Groq no la tiene, por eso esta lectura va directo a OpenRouter (modelo gratuito con visión).
MODELO_VISION = "google/gemma-4-31b-it:free"

MAX_BYTES_IMAGEN = 1_500_000  # el cliente ya comprime a ~300-800 KB; esto es un tope duro
FORMATOS = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG", "image/webp": b"RIFF"}


class FacturaError(Exception):
    """Error con mensaje apto para mostrar al usuario y su código HTTP."""

    def __init__(self, mensaje: str, status: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status


def validar_imagen(imagen_base64: str, mime: str) -> bytes:
    """Decodifica y valida tamaño y tipo real (por firma, no por lo que diga el cliente)."""
    if mime not in FORMATOS:
        raise FacturaError("Formato no soportado. Usa una foto JPG, PNG o WebP.")
    if len(imagen_base64) > MAX_BYTES_IMAGEN * 4 // 3 + 16:
        raise FacturaError("La imagen es muy pesada. Toma la foto de nuevo o usa una más pequeña.", 413)
    try:
        datos = base64.b64decode(imagen_base64, validate=True)
    except Exception:
        raise FacturaError("No pudimos leer la imagen enviada.")
    if not datos or len(datos) > MAX_BYTES_IMAGEN:
        raise FacturaError("La imagen es muy pesada. Toma la foto de nuevo o usa una más pequeña.", 413)
    if not datos.startswith(FORMATOS[mime]):
        raise FacturaError("El archivo no parece una imagen válida.")
    return datos


def _prompt(categorias: list[str]) -> str:
    return (
        "Eres un lector de facturas y recibos de Colombia. Mira la imagen y responde SOLO un JSON "
        "(sin texto extra, sin markdown) con estas llaves: "
        '"legible" (true/false: false si la foto está borrosa, cortada o no es una factura), '
        '"comercio" (nombre del establecimiento), "fecha" (AAAA-MM-DD o null), '
        '"total" (número final pagado, sin símbolos ni separadores de miles, o null si no se ve), '
        '"impuestos" (IVA/impoconsumo como número o null), "propina" (número o null), '
        '"moneda" (código ISO, COP por defecto), '
        f'"categoria" (EXACTAMENTE una de: {", ".join(categorias) or "Otros"}). '
        "No inventes cifras: si no estás seguro de un dato, usa null."
    )


def _numero(v) -> float | None:
    """Convierte lo que devuelva el modelo ('1.250.000', '45,900', 12500) a número."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v >= 0 else None
    s = re.sub(r"[^\d.,]", "", str(v))
    if not s:
        return None
    # Último separador seguido de 1-2 dígitos = decimales; el resto son miles.
    m = re.search(r"[.,](\d{1,2})$", s)
    if m:
        entero = re.sub(r"[.,]", "", s[: m.start()])
        return float(f"{entero or '0'}.{m.group(1)}")
    return float(re.sub(r"[.,]", "", s))


def _fecha(v) -> str | None:
    if not v:
        return None
    try:
        d = datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    # Una fecha futura o absurda casi seguro es una lectura equivocada.
    if d > date.today() or d.year < 2000:
        return None
    return d.isoformat()


def parsear_respuesta(texto: str, categorias: list[str]) -> dict:
    """Limpia y valida el JSON del modelo. Lanza FacturaError si no hay total legible."""
    texto = re.sub(r"```(?:json)?", "", texto or "").strip()
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    try:
        crudo = json.loads(m.group(0)) if m else {}
    except ValueError:
        crudo = {}
    if not isinstance(crudo, dict) or crudo.get("legible") is False:
        raise FacturaError("La foto no se ve clara. Intenta con más luz y la factura completa, sin movimiento.", 422)

    total = _numero(crudo.get("total"))
    if not total or total <= 0:
        raise FacturaError(
            "No encontramos el total en la foto. Intenta de nuevo con la factura completa o escribe el monto a mano.", 422
        )
    moneda = str(crudo.get("moneda") or "COP").upper().strip()
    if not re.fullmatch(r"[A-Z]{3}", moneda):
        moneda = "COP"
    categoria = crudo.get("categoria")
    return {
        "comercio": str(crudo.get("comercio") or "").strip()[:80],
        "fecha": _fecha(crudo.get("fecha")),
        "total": total,
        "impuestos": _numero(crudo.get("impuestos")),
        "propina": _numero(crudo.get("propina")),
        "moneda": moneda,
        "categoria_ia": categoria if categoria in categorias else None,
    }


def analizar_factura(datos: bytes, mime: str, categorias: list[str]) -> dict:
    """Envía la imagen al modelo de visión y devuelve los campos ya validados."""
    if not settings.openrouter_api_key:
        raise FacturaError("La lectura de facturas no está disponible en este momento.", 503)

    url_imagen = f"data:{mime};base64,{base64.b64encode(datos).decode()}"
    try:
        resp = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={
                "model": MODELO_VISION,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _prompt(categorias)},
                        {"type": "image_url", "image_url": {"url": url_imagen}},
                    ],
                }],
                "temperature": 0.1,
                "max_tokens": 600,
            },
            timeout=45,
        )
        resp.raise_for_status()
        texto = resp.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        raise FacturaError("No pudimos leer la factura ahora. Intenta de nuevo en un momento.", 502)
    return parsear_respuesta(texto, categorias)
