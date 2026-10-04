"""
Detección de extractos bancarios y notificaciones de transacciones en Gmail.

Todo lo que no necesita red vive aquí (consultas de búsqueda, filtrado por
remitente, lectura de adjuntos, apertura de PDFs con clave, sugerencia de
cuenta) para poder probarlo con correos y PDFs simulados, sin llamar a Google.

Privacidad: el alcance OAuth sigue siendo gmail.readonly. Nunca se guarda el
PDF ni el cuerpo del correo; solo metadatos (banco, periodo, estado). La clave
de los PDFs se maneja cifrada y NUNCA se escribe en logs.
"""
import base64
import io
import re
import unicodedata
from datetime import datetime

import pdfplumber

# ── Remitentes conocidos ────────────────────────────────────────────
# Para ampliar la cobertura basta con agregar una línea: dominio -> nombre.
# Se compara contra el dominio del remitente y sus subdominios
# (p. ej. "alertas.bancolombia.com.co" coincide con "bancolombia.com.co").
DOMINIOS_BANCOS: dict[str, str] = {
    "bancolombia.com.co": "Bancolombia",
    "grupobancolombia.com": "Bancolombia",
    "davivienda.com": "Davivienda",
    "davivienda.com.co": "Davivienda",
    "bbva.com.co": "BBVA Colombia",
    "bbva.com": "BBVA Colombia",
    "bancodebogota.com.co": "Banco de Bogotá",
    "bancodebogota.com": "Banco de Bogotá",
    "nequi.com.co": "Nequi",
    "nequi.com": "Nequi",
    "daviplata.com": "Daviplata",
    "lulobank.com": "Lulo Bank",
    "lulo.com.co": "Lulo Bank",
    "nu.com.co": "Nu Colombia",
    "nubank.com.co": "Nu Colombia",
    "rappipay.co": "RappiPay",
    "rappipay.com": "RappiPay",
    "bancofalabella.com.co": "Banco Falabella",
    "falabella.com.co": "Banco Falabella",
    "scotiabankcolpatria.com": "Scotiabank Colpatria",
    "colpatria.com": "Scotiabank Colpatria",
    "avvillas.com.co": "Banco AV Villas",
    "itau.co": "Itaú",
    "itau.com.co": "Itaú",
    "bancodeoccidente.com.co": "Banco de Occidente",
    "bancopopular.com.co": "Banco Popular",
    "bancocajasocial.com": "Banco Caja Social",
    "bancoomeva.com.co": "Bancoomeva",
    "serfinanza.com.co": "Banco Serfinanza",
    "tuya.com.co": "Tuya",
    "movii.com.co": "Movii",
    "bancopichincha.com.co": "Banco Pichincha",
    "pichincha.com.co": "Banco Pichincha",
    "gnbsudameris.com.co": "GNB Sudameris",
    "bancow.com.co": "Banco W",
    "finandina.com": "Finandina",
    "uala.com.co": "Ualá",
}

# Palabras que identifican un extracto en el asunto o en el nombre del adjunto.
PALABRAS_EXTRACTO = (
    "extracto",
    "estado de cuenta",
    "estado de tu cuenta",
    "resumen de cuenta",
    "resumen de tu cuenta",
    "resumen mensual",
)

# Palabras que indican una notificación de transacción (no publicidad).
PALABRAS_TRANSACCION = (
    "compra", "pago", "transferencia", "retiro", "consignaci", "recibiste",
    "enviaste", "abono", "débito", "debito", "crédito", "credito",
    "transacci", "te enviaron", "movimiento", "avance",
)

MAX_PDF_BYTES = 15 * 1024 * 1024


def _sin_acentos(texto: str) -> str:
    n = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in n if unicodedata.category(c) != "Mn").lower()


# ── Consultas de búsqueda ───────────────────────────────────────────

def _grupo_remitentes() -> str:
    return " OR ".join(sorted(DOMINIOS_BANCOS))


def _ventana(dias: int, desde: datetime | None) -> str:
    """Con `desde` se busca desde esa fecha (sincronización incremental);
    sin ella, los últimos `dias` días."""
    return f"after:{desde:%Y/%m/%d}" if desde else f"newer_than:{dias}d"


def construir_query_extractos(dias: int = 180, desde: datetime | None = None) -> str:
    palabras = " OR ".join(f'"{p}"' if " " in p else p for p in PALABRAS_EXTRACTO)
    return (
        f"has:attachment filename:pdf {_ventana(dias, desde)} "
        f"(({palabras}) OR from:({_grupo_remitentes()}))"
    )


def construir_query_notificaciones(dias: int = 14, desde: datetime | None = None) -> str:
    return f"from:({_grupo_remitentes()}) {_ventana(dias, desde)} -has:attachment"


# ── Remitente / clasificación de correos ────────────────────────────

def dominio_de(remitente: str) -> str:
    m = re.search(r"@([A-Za-z0-9.\-]+)", remitente or "")
    return m.group(1).lower() if m else ""


def banco_por_remitente(remitente: str) -> str | None:
    dominio = dominio_de(remitente)
    if not dominio:
        return None
    for base, nombre in DOMINIOS_BANCOS.items():
        if dominio == base or dominio.endswith("." + base):
            return nombre
    return None


def contiene_palabra_extracto(*textos: str) -> bool:
    junto = _sin_acentos(" ".join(t or "" for t in textos))
    return any(_sin_acentos(p) in junto for p in PALABRAS_EXTRACTO)


def es_notificacion_transaccion(asunto: str, snippet: str) -> bool:
    junto = _sin_acentos(f"{asunto} {snippet}")
    return any(_sin_acentos(p) in junto for p in PALABRAS_TRANSACCION)


def encabezados(msg: dict) -> dict:
    return {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}


def fecha_mensaje(msg: dict) -> datetime | None:
    try:
        return datetime.utcfromtimestamp(int(msg["internalDate"]) / 1000)
    except (KeyError, ValueError, TypeError):
        return None


def listar_adjuntos_pdf(msg: dict) -> list[dict]:
    """Recorre las partes MIME y devuelve los PDF adjuntos:
    [{"archivo", "attachment_id", "tamano"}]."""
    encontrados: list[dict] = []

    def recorrer(parte: dict):
        nombre = parte.get("filename") or ""
        cuerpo = parte.get("body", {}) or {}
        es_pdf = nombre.lower().endswith(".pdf") or parte.get("mimeType") == "application/pdf"
        if nombre and es_pdf and cuerpo.get("attachmentId"):
            encontrados.append({
                "archivo": nombre,
                "attachment_id": cuerpo["attachmentId"],
                "tamano": cuerpo.get("size", 0),
            })
        for hija in parte.get("parts", []) or []:
            recorrer(hija)

    recorrer(msg.get("payload", {}))
    return encontrados


def descargar_adjunto(gmail, msg_id: str, attachment_id: str) -> bytes:
    data = (
        gmail.users().messages().attachments()
        .get(userId="me", messageId=msg_id, id=attachment_id)
        .execute()
        .get("data", "")
    )
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


# ── Apertura y análisis del PDF ─────────────────────────────────────

def claves_candidatas(clave_guardada: str | None) -> list[str]:
    """El usuario puede guardar varias claves separadas por coma (p. ej. su
    cédula y la de su pareja). Siempre se prueba primero sin clave."""
    claves = [""]
    if clave_guardada:
        claves += [c.strip() for c in clave_guardada.split(",") if c.strip()]
    return claves


def abrir_pdf(pdf_bytes: bytes, claves: list[str]) -> tuple[str, str, str | None]:
    """Intenta abrir el PDF con cada clave. Devuelve (estado, texto, clave_usada):
    estado = 'ok' | 'falta_clave' | 'error'. Nunca registra las claves."""
    if not pdf_bytes or len(pdf_bytes) > MAX_PDF_BYTES:
        return "error", "", None
    hubo_clave_incorrecta = False
    for clave in claves:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes), password=clave or None) as pdf:
                texto = "\n".join((p.extract_text() or "") for p in pdf.pages[:6])
            return "ok", texto, clave or None
        except Exception as exc:  # noqa: BLE001
            # pdfplumber envuelve el error de pdfminer (PDFPasswordIncorrect) en
            # PdfminerException; el original viene en exc.args[0].
            causas = [exc, *[a for a in exc.args if isinstance(a, BaseException)]]
            if any("Password" in type(c).__name__ for c in causas):
                hubo_clave_incorrecta = True
                continue
            return "error", "", None
    return ("falta_clave" if hubo_clave_incorrecta else "error"), "", None


_MESES = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre"
_FECHA_DMY = r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}"
_FECHA_YMD = r"\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}"
_RANGO = re.compile(
    rf"({_FECHA_DMY}|{_FECHA_YMD})\s*(?:a|al|hasta|-|–)\s*({_FECHA_DMY}|{_FECHA_YMD})", re.IGNORECASE
)
_MES_ANIO = re.compile(rf"\b({_MESES})\s+(?:de\s+)?(20\d{{2}})\b", re.IGNORECASE)


def detectar_periodo(texto: str, respaldo: str = "") -> str:
    m = _RANGO.search(texto or "")
    if m:
        return f"{m.group(1)} a {m.group(2)}"
    m = _MES_ANIO.search(_sin_acentos(texto or ""))
    if m:
        return f"{m.group(1)} {m.group(2)}"
    m = _MES_ANIO.search(_sin_acentos(respaldo or ""))
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return ""


_ULTIMOS4 = [
    re.compile(r"terminad[ao]\s+en\s*\D{0,3}(\d{4})\b", re.IGNORECASE),
    re.compile(r"(?:\*{2,}|[xX]{2,})[\s\-]*(\d{4})\b"),
    re.compile(r"(?:cuenta|tarjeta|producto)[^\n\d]{0,30}(\d[\d\- ]{5,22}\d)", re.IGNORECASE),
]


def detectar_ultimos4(texto: str) -> str:
    for patron in _ULTIMOS4:
        m = patron.search(texto or "")
        if m:
            digitos = re.sub(r"\D", "", m.group(1))
            if len(digitos) >= 4:
                return digitos[-4:]
    return ""


def sugerir_cuenta(banco: str, ultimos4: str, cuentas: list) -> str | None:
    """Elige la cuenta del usuario que mejor encaja con el extracto. Compara
    el nombre del banco (sin acentos) y, si lo hay, los últimos 4 dígitos con
    el nombre de la cuenta. Solo devuelve algo si hay un ganador claro."""
    banco_n = _sin_acentos(banco)
    palabras = [p for p in re.split(r"\W+", banco_n) if len(p) >= 4 and p not in ("banco", "colombia")]
    puntajes: list[tuple[int, object]] = []
    for c in cuentas:
        nombre = _sin_acentos(getattr(c, "nombre", ""))
        puntaje = 0
        if banco_n and banco_n in nombre:
            puntaje += 2
        elif any(p in nombre for p in palabras):
            puntaje += 2
        if ultimos4 and ultimos4 in nombre:
            puntaje += 3
        if puntaje:
            puntajes.append((puntaje, c))
    if not puntajes:
        return None
    puntajes.sort(key=lambda x: -x[0])
    if len(puntajes) > 1 and puntajes[0][0] == puntajes[1][0]:
        return None
    return puntajes[0][1].id
