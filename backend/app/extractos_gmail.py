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

from app.cuentas_banco import filtrar_por_producto, producto_de_cuenta, producto_de_texto

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
    # Remitentes reales que NO son subdominio del dominio principal del banco.
    "notificacionesbancolombia.com.co": "Bancolombia",
    "notificacionesbancolombia.com": "Bancolombia",  # alertasynotificaciones@ (el remitente real de las alertas)
    "bancolombia.com": "Bancolombia",
    "nequi.co": "Nequi",
    "nu.com": "Nu Colombia",
    "nubank.com": "Nu Colombia",
    "daviplata.com.co": "Daviplata",
    "davibank.com": "Davivienda",
    "rappicard.co": "RappiPay",
    "rappicard.com.co": "RappiPay",
    "bancodeoccidente.com": "Banco de Occidente",
    "bbvanet.com.co": "BBVA Colombia",
    "scotiabank.com.co": "Scotiabank Colpatria",
    "movii.com": "Movii",
}

# Palabras con las que el usuario suele nombrar su cuenta de cada banco o
# billetera (además del nombre completo). Las cortas se buscan como palabra
# entera: "nu" encuentra "Nu" y "Mi Nu", no "menú".
ALIAS_BANCOS: dict[str, tuple[str, ...]] = {
    "nu colombia": ("nu", "nubank"),
    "rappipay": ("rappi", "rappicard", "rappipay"),
    "lulo bank": ("lulo", "lulobank"),
    "bbva colombia": ("bbva",),
    "scotiabank colpatria": ("scotiabank", "colpatria"),
    "banco de bogota": ("bogota",),
    "banco falabella": ("falabella",),
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
    "pagaste", "te pagaron", "retiraste", "cobro", "cobramos", "devoluci", "reembolso", "rendimiento",
)

# Frases de asunto de notificaciones de transacción (Nu y similares); se buscan sin importar el remitente.
FRASES_ASUNTO_TRANSACCION = (
    "pagaste con", "compraste con", "compraste en", "pagaste en", "recibiste una transferencia", "te enviaron",
)

# Nombres con los que un banco digital firma el remitente cuando su dominio no está en la lista.
_NOMBRES_REMITENTE = {"nu": "Nu Colombia", "nubank": "Nu Colombia", "nu colombia": "Nu Colombia"}

MAX_PDF_BYTES = 15 * 1024 * 1024


def _sin_acentos(texto: str) -> str:
    n = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in n if unicodedata.category(c) != "Mn").lower()


# ── Consultas de búsqueda ───────────────────────────────────────────

def dominios_de_pais(pais: str | None = "CO") -> dict[str, str]:
    """Remitentes de un país. CO (por defecto, comportamiento de siempre) usa DOMINIOS_BANCOS;
    los demás salen del registro app/paises.py."""
    from app import paises

    if (pais or "CO").upper() == "CO":
        return DOMINIOS_BANCOS
    return paises.dominios_del_pais(pais)


def _grupo_remitentes(pais: str | None = "CO") -> str:
    return " OR ".join(sorted(dominios_de_pais(pais)))


def _ventana(dias: int, desde: datetime | None) -> str:
    """Con `desde` se busca desde esa fecha (sincronización incremental);
    sin ella, los últimos `dias` días."""
    return f"after:{desde:%Y/%m/%d}" if desde else f"newer_than:{dias}d"


def construir_query_extractos(dias: int = 180, desde: datetime | None = None, pais: str | None = "CO") -> str:
    palabras = " OR ".join(f'"{p}"' if " " in p else p for p in PALABRAS_EXTRACTO)
    return (
        f"has:attachment filename:pdf {_ventana(dias, desde)} "
        f"(({palabras}) OR from:({_grupo_remitentes(pais)}))"
    )


def construir_query_notificaciones(dias: int = 14, desde: datetime | None = None, pais: str | None = "CO") -> str:
    # Además de los remitentes conocidos, el ASUNTO de las notificaciones que los bancos digitales mandan desde
    # dominios que cambian («Pagaste con tu Cuenta de ahorros Nu»): así no depende de acertar el dominio.
    asuntos = " OR ".join(f'"{f}"' for f in FRASES_ASUNTO_TRANSACCION)
    return f"(from:({_grupo_remitentes(pais)}) OR subject:({asuntos})) {_ventana(dias, desde)} -has:attachment"


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
    # Otros países (remitentes sin probar con correos reales): solo se reconoce el banco;
    # la consulta a Gmail pide los de CO salvo que se pase `pais`.
    from app import paises

    for base, nombre in paises.todos_los_dominios().items():
        if dominio == base or dominio.endswith("." + base):
            return nombre
    m = re.match(r'^\s*"?([^"<@]+?)"?\s*<', remitente or "")
    return _NOMBRES_REMITENTE.get(_sin_acentos(m.group(1)).strip()) if m else None


def contiene_palabra_extracto(*textos: str) -> bool:
    junto = _sin_acentos(" ".join(t or "" for t in textos))
    return any(_sin_acentos(p) in junto for p in PALABRAS_EXTRACTO)


# Avisos de un banco que mencionan «pago», «tarjeta» o «movimientos» pero NO son una transacción:
# el extracto está listo (va por el carril de extractos), se agregó una tarjeta al celular, un pago
# que NO se hizo por falta de fondos, seguridad, publicidad. No se ofrecen para aprobar como movimiento.
PALABRAS_AVISO_NO_TRANSACCION = (
    "extracto", "estado de cuenta", "agregaste tu tarjeta", "tarjeta virtual", "estamos creando tu tarjeta",
    "faltan fondos", "fondos insuficientes", "no pudimos", "no se pudo", "rechazad", "declinad",
    "novedades", "preaprobad", "oferta", "promoci", "inicio de sesion", "acceso a tu", "codigo de verificacion",
    "clave dinamica", "actualiza tu", "pedido fue entregado", "retirar tu compra",
    "sin cobro", "encuesta", "te invitamos",
)


def es_aviso_no_transaccion(asunto: str, snippet: str = "") -> bool:
    """True si el correo es un aviso (extracto listo, tarjeta agregada, pago fallido, publicidad...) y no
    una transacción. Se mira sobre todo el ASUNTO; el fragmento solo para «faltan fondos» y similares."""
    a = _sin_acentos(asunto)
    if any(p in a for p in PALABRAS_AVISO_NO_TRANSACCION) or contiene_palabra_extracto(asunto):
        return True
    s = _sin_acentos(snippet)
    return any(p in s for p in ("faltan fondos", "fondos insuficientes", "no se pudo completar", "fue rechazad"))


def es_notificacion_transaccion(asunto: str, snippet: str) -> bool:
    if es_aviso_no_transaccion(asunto, snippet):
        return False
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


def _claves_banco(banco: str) -> tuple[str, list[str]]:
    """(nombre normalizado, palabras con las que se busca en el nombre de la cuenta)."""
    banco_n = _sin_acentos(banco)
    palabras = [p for p in re.split(r"\W+", banco_n) if len(p) >= 4 and p not in ("banco", "colombia")]
    return banco_n, palabras + list(ALIAS_BANCOS.get(banco_n, ()))


def _puntaje_banco(banco_n: str, palabras: list[str], nombre: str) -> int:
    if not banco_n:
        return 0
    if banco_n in nombre:
        return 2
    for p in palabras:
        if re.search(rf"\b{re.escape(p)}\b", nombre) or (len(p) >= 4 and p in nombre):
            return 2
    return 0


def cuentas_del_banco(banco: str, cuentas: list) -> list:
    """Cuentas del usuario cuyo nombre corresponde al banco/billetera (puede
    haber varias). Vacío si no tiene ninguna: ahí hay que crearla, no adivinar."""
    banco_n, palabras = _claves_banco(banco)
    return [c for c in cuentas if _puntaje_banco(banco_n, palabras, _sin_acentos(getattr(c, "nombre", "")))]


def inferir_cuenta_por_remitente(remitente: str, cuentas: list, texto: str = "") -> tuple[str | None, str | None, bool]:
    """(banco, cuenta_sugerida_id, falta_cuenta) para una notificación de correo.
    Sin banco reconocido no se adivina nada: el usuario debe elegir. Si el
    banco se reconoce pero el usuario no tiene cuenta de ese banco,
    `falta_cuenta` es True (hay que crearla, no asignar otra)."""
    banco = banco_por_remitente(remitente)
    if not banco:
        return None, None, False
    if not cuentas_del_banco(banco, cuentas):
        return banco, None, True
    return banco, sugerir_cuenta(banco, detectar_ultimos4(texto), cuentas, texto), False


def _ultimos4_de_cuenta(cuenta) -> set[str]:
    """Últimos 4 dígitos que la cuenta declara: en el alias de la tarjeta o en el nombre."""
    bruto = f"{getattr(cuenta, 'alias_tarjeta', '') or ''} {getattr(cuenta, 'nombre', '') or ''}"
    return set(re.findall(r"(?<!\d)(\d{4})(?!\d)", bruto))


def candidatas_banco(banco: str, ultimos4: str, cuentas: list, texto: str = "") -> tuple[list, str | None]:
    """(cuentas del banco que siguen en pie, producto detectado) tras usar dígitos y TIPO.
    Si queda más de una, es ambiguo y hay que preguntar (nunca adivinar)."""
    cands = cuentas_del_banco(banco, cuentas)
    producto = producto_de_texto(texto)
    if len(cands) > 1 and ultimos4:
        con_digitos = [c for c in cands if ultimos4 in _ultimos4_de_cuenta(c)]
        if con_digitos:
            return con_digitos, producto
    if len(cands) > 1:
        cands = filtrar_por_producto(cands, producto)
    return cands, producto


# ── Datos del CUERPO del correo de la tarjeta (sin abrir el PDF) ─────────────────────────────────
_MES_PAL = r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
_DIA_MES = rf"(\d{{1,2}}\s+(?:de\s+)?{_MES_PAL}(?:\s+(?:de[l]?\s+)?20\d{{2}})?)"


def texto_cuerpo(msg: dict, tope: int = 20000) -> str:
    """Texto plano del cuerpo del correo (text/plain; si no hay, el HTML sin etiquetas). Solo para leer
    unos pocos datos al vuelo: el cuerpo NO se guarda."""
    import html as _html

    plano, web = [], []

    def recorrer(parte: dict):
        cuerpo = (parte.get("body") or {}).get("data")
        tipo = (parte.get("mimeType") or "").lower()
        if cuerpo and tipo in ("text/plain", "text/html"):
            try:
                t = base64.urlsafe_b64decode(cuerpo + "=" * (-len(cuerpo) % 4)).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                t = ""
            (plano if tipo == "text/plain" else web).append(t)
        for hija in parte.get("parts", []) or []:
            recorrer(hija)

    recorrer(msg.get("payload", {}) or {})
    if plano:
        t = "\n".join(plano)
    else:
        t = _html.unescape(re.sub(r"<[^>]+>", " ", "\n".join(web)))
    return re.sub(r"[ \t\r\f\v ]+", " ", t)[:tope]


def datos_cuerpo_tarjeta(texto: str) -> dict | None:
    """Pago mínimo, período facturado, fecha de corte y fecha límite que trae el CUERPO del aviso de la
    tarjeta de crédito. Solo lo que tiene etiqueta clara; las fechas se guardan tal cual vienen (sin año
    no se inventa). None si no hay nada o el correo no habla de una tarjeta."""
    from app.extracto_tarjeta import leer_datos_tarjeta

    t = _sin_acentos(texto or "")
    if "tarjeta" not in t:
        return None
    out: dict = {}
    pm = leer_datos_tarjeta(texto).get("pago_minimo")
    if pm:
        out["pago_minimo"] = pm
    m = re.search(rf"periodo\s+facturado\s*[:\-]?\s*{_DIA_MES}\s*(?:-|–|a|al|hasta)\s*{_DIA_MES}", t)
    if m:
        out["periodo_facturado"] = f"{m.group(1)} - {m.group(2)}"
    m = re.search(rf"fecha\s+de\s+corte\s*[:\-]?\s*{_DIA_MES}", t)
    if m:
        out["fecha_corte"] = m.group(1)
    m = re.search(rf"fecha\s+limite\s+de\s+pago\s*[:\-]?\s*{_DIA_MES}", t)
    if m:
        out["fecha_limite"] = m.group(1)
    return out or None


def asunto_para_gmail(texto: str, maximo: int = 80) -> str | None:
    """Texto del cliente -> frase segura para `subject:"…"`. Sin comillas, barras, llaves, paréntesis ni
    caracteres de control: dentro de la frase nada se interpreta como operador de Gmail. None si queda
    demasiado corto."""
    t = re.sub(r"[\x00-\x1f\x7f\"\\{}()<>]", " ", texto or "")
    t = re.sub(r"\s+", " ", t).strip()[:maximo].strip()
    return t if len(t) >= 3 else None


def construir_query_asunto(asunto: str, dias: int = 365) -> str:
    return f'has:attachment filename:pdf newer_than:{dias}d subject:"{asunto}"'


def sugerir_cuenta(banco: str, ultimos4: str, cuentas: list, texto: str = "") -> str | None:
    """Elige la cuenta del usuario que mejor encaja con el extracto/correo. Compara
    el nombre del banco (sin acentos); si el banco tiene varias cuentas desempata con los
    últimos 4 dígitos (en el alias o el nombre) y con el TIPO que insinúa el `texto`
    (tarjeta de crédito/cupo/pago mínimo -> crédito; cuenta de ahorros/Cajita -> débito).
    Solo devuelve algo si hay un ganador claro."""
    cands, producto = candidatas_banco(banco, ultimos4, cuentas, texto)
    if len(cands) != 1:
        return None
    # Una sola cuenta del banco no basta: si el extracto es de OTRO producto (p. ej. la tarjeta de crédito
    # Nu y la persona solo tiene la cuenta Nu de ahorros), asignarlo allí taparía el extracto de esa cuenta.
    # (los últimos 4 dígitos que coinciden con el alias de la cuenta mandan sobre el tipo que insinúa el texto)
    if producto and producto_de_cuenta(cands[0]) not in (producto, None) and ultimos4 not in _ultimos4_de_cuenta(cands[0]):
        return None
    return cands[0].id
