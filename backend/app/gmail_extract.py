"""
Extracción de monto/moneda/comercio desde el texto de un correo bancario.
Patrones regex migrados de extractAmount_/extractCurrency_/extractMerchant_
en Código.js (Apps Script), probados contra bancos y comercios colombianos.
"""
import re

_AMOUNT_PATTERNS = [
    # Nequi/Bre-B y similares escriben el monto SIN «$»: «Recibiste 30.000 de ...», «Enviaste de manera
    # exitosa 45.500 a la llave ...». Con contexto, para no confundir con años, horas o teléfonos.
    re.compile(
        r"(?:recibiste|te\s+enviaron|te\s+transfirieron|enviaste(?:\s+de\s+manera\s+exitosa)?|"
        r"transferiste(?:\s+de\s+manera\s+exitosa)?|pagaste)\s+(?:\$\s*)?"
        r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d{3,})(?![\d.,]*\d)",
        re.IGNORECASE,
    ),
    re.compile(r"cantidad\s*de\s*[:\s]*\$?\s*([\d.,]+)", re.IGNORECASE),
    re.compile(
        r"(?:valor|monto|total|cobro|pago|precio|transacci[oó]n|compra|d[eé]bito|"
        r"cr[eé]dito|importe|cargo|deduccion|descuento|retiro|consignaci[oó]n)"
        r"\s*[:\s]*(?:de\s*)?(?:COP\s*)?\$?\s*([\d.,]+)",
        re.IGNORECASE,
    ),
    re.compile(r"\$\s*([\d.,]+)"),
    re.compile(r"COP\s*([\d.,]+)", re.IGNORECASE),
    re.compile(r"USD\s*([\d.,]+)", re.IGNORECASE),
    re.compile(r"EUR\s*([\d.,]+)", re.IGNORECASE),
    re.compile(r"([\d.,]+)\s*COP", re.IGNORECASE),
    # Respaldo: número con miles agrupados («30.000», «1.250.000»). Va ANTES del de 3-4 dígitos sueltos,
    # que leía «1.250.000» como 250.000 y «45.500» como 500.
    re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+(?:,\d{2})?)(?![\d])"),
    re.compile(r"\b(\d{3,4}(?:[.,]\d{3})*(?:[.,]\d{2})?)\b"),
]

_BANK_MAP = [
    # Bancos y entidades financieras vigiladas (Colombia)
    ("bancolombia", "Bancolombia"),
    ("davivienda", "Davivienda"),
    ("nequi", "Nequi"),
    ("daviplata", "Daviplata"),
    ("bbva", "BBVA Colombia"),
    ("scotiabank", "Scotiabank Colpatria"),
    ("colpatria", "Scotiabank Colpatria"),
    ("itau", "Itaú"),
    ("itaú", "Itaú"),
    ("av villas", "Banco AV Villas"),
    ("bogota", "Banco de Bogotá"),
    ("occidente", "Banco de Occidente"),
    ("popular", "Banco Popular"),
    ("caja social", "Banco Caja Social"),
    ("banco falabella", "Banco Falabella"),
    ("pichincha", "Banco Pichincha"),
    ("banco agrario", "Banco Agrario"),
    ("bancamia", "Bancamía"),
    ("banco w", "Banco W"),
    ("coltefinanciera", "Coltefinanciera"),
    ("confiar", "Confiar"),
    ("bancoomeva", "Bancoomeva"),
    ("serfinanza", "Banco Serfinanza"),
    ("tuya", "Tuya"),
    ("cotrafa", "Cotrafá"),
    ("finandina", "Finandina"),
    ("mibanco", "Mibanco"),
    ("lulo", "Lulo Bank"),
    ("nubank", "Nu Colombia"),
    ("nu.com", "Nu Colombia"),
    ("movii", "Movii"),
    ("rappipay", "RappiPay"),
    ("rappicard", "RappiCard"),
    ("uala", "Ualá"),
    ("tpaga", "Tpaga"),
    ("dale", "Dale!"),
]

# Comercios y servicios que escriben ellos mismos: si el remitente es uno de estos, ES el comercio.
_COMERCIO_MAP = [
    ("falabella.com", "Falabella"),
    ("rappi", "Rappi"),
    ("paypal", "PayPal"),
    ("mercadopago", "MercadoPago"),
    ("claro", "Claro"),
    ("movistar", "Movistar"),
    ("tigo", "Tigo"),
    ("directv", "DirecTV"),
    ("netflix", "Netflix"),
    ("spotify", "Spotify"),
    ("amazon", "Amazon"),
    ("apple", "Apple"),
    ("google", "Google"),
    ("uber", "Uber"),
    ("didi", "DiDi"),
    ("ifood", "iFood"),
]

# Concepto del movimiento leído del asunto/cuerpo. Cada patrón captura el nombre (comercio o
# persona); el prefijo es lo que se antepone para que la descripción se lea sola.
# El nombre termina en puntuación o en una palabra de "detalle" (por, con, el, desde...).
_FIN = r"(?=[,;.\n]|\s+(?:por|con|desde|de\s+tu|a\s+las|el\s+(?:\d|d[ií]a)|valor|usando|cuenta|tarjeta|COP|USD)\b|\s+\$|\s*$)"
_NOMBRE = r"([A-Za-zÀ-ú0-9*][^,;.\n$]{1,38}?)"
_CONCEPTOS = [
    (re.compile(r"compra\s+(?:(?:exitosa|aprobada|realizada)\s+)?(?:por\s+(?:\$|COP|USD|EUR)?\s*[\d.,]+\s+)?(?:en|con\s+tu\s+tarjeta\s+en)\s+" + _NOMBRE + _FIN, re.IGNORECASE), "Compra en "),
    (re.compile(r"(?:enviaste|env[ií]o|transferiste|transferencia)\s+(?:de\s+manera\s+exitosa\s+)?(?:de\s+)?(?:\$?\s*[\d.,]+\s+)?a\s+(?:la\s+llave\s+\S+\s+de\s+)?" + _NOMBRE + _FIN, re.IGNORECASE), "Envío a "),
    (re.compile(r"(?:recibiste|te\s+enviaron|te\s+transfirieron)\s+(?:\$?\s*[\d.,]+\s+)?de\s+" + _NOMBRE + _FIN, re.IGNORECASE), "Recibido de "),
    (re.compile(r"pago\s+de\s+(servicios?\s+p[uú]blicos|servicios?|factura|impuestos?|pensi[oó]n|matr[ií]cula|arriendo|cuota)", re.IGNORECASE), "Pago de "),
    (re.compile(r"(?:recibo|factura)\s+de\s+" + _NOMBRE + _FIN, re.IGNORECASE), "Pago de "),
    (re.compile(r"pago\s+(?:en|a)\s+" + _NOMBRE + _FIN, re.IGNORECASE), "Pago a "),
    (re.compile(r"establecimiento[:\s]+" + _NOMBRE + _FIN, re.IGNORECASE), "Compra en "),
    (re.compile(r"retiro\s+(?:en\s+)?(cajero|corresponsal)", re.IGNORECASE), "Retiro en "),
]
_ASTERISCO = re.compile(r"\*([A-Z][A-Z0-9 ]{2,25})\*")

_INGRESO_RE = re.compile(
    r"recibiste|te enviaron|te pagaron|consignaron|te consignaron|abono|dep[oó]sito|devoluci[oó]n|reembolso|reversi[oó]n|rendimientos?",
    re.IGNORECASE,
)
_EGRESO_RE = re.compile(r"enviaste|transferiste|pagaste|pago|compra|retiro|retiraste|d[eé]bito|cargo|cobro|cobramos|avance", re.IGNORECASE)
_TRANSFER_RE = re.compile(
    r"transferencia\s+entre|transferiste a tu|traslado entre cuentas|entre\s+(?:tus|sus)\s+cuentas|cuentas\s+propias|"
    r"(?:pag[óo]|pagaste)\s+.{0,40}?\s+a\s+(?:tu|su)\s+tarjeta",
    re.IGNORECASE,
)


def _parse_num(raw: str) -> float:
    """Convierte '1.234.567,50' o '1,234,567.50' o '1234567' a float."""
    raw = raw.strip()
    partes = re.split(r"[.,]", raw)
    if len(partes) > 1 and len(partes[-1]) <= 2 and len(partes) > 1:
        entero = "".join(partes[:-1])
        decimal = partes[-1]
        try:
            return float(f"{entero}.{decimal}")
        except ValueError:
            return 0.0
    limpio = re.sub(r"[.,]", "", raw)
    try:
        return float(limpio)
    except ValueError:
        return 0.0


def _parece_anio(crudo: str, n: float) -> bool:
    """Una cifra suelta de 4 dígitos entre 1990 y 2100 sin separadores es un año, no un monto."""
    return crudo.isdigit() and len(crudo) == 4 and 1990 <= n <= 2100


# Cuántos patrones del final son «cifras sueltas» (sin ninguna palabra de contexto): el modo estricto
# no los usa. En el CUERPO de un correo hay números de cuenta, NIT, teléfonos y códigos que no son dinero
# (un aviso de extracto llegó a leerse como $901.658.107).
_CIFRAS_SUELTAS = 2
MONTO_MAXIMO_ESTRICTO = 500_000_000


# Identificadores que NO son dinero: «NIT 901.658.107-1», «cuenta 1234567890», «CC 1.020.304.050», teléfonos,
# referencias. Se quitan del texto antes de buscar el monto (un NIT de Nu llegó a leerse como $901.658.107).
_DOCUMENTOS = re.compile(
    r"(?:\bn\.?\s?i\.?\s?t\.?|\bc\.?\s?c\.?|\bc[eé]dula|\bidentificaci[oó]n|\bdocumento|\bcuenta|\bcta\.?|\bcelular|"
    r"\btel[eé]fono|\btel\.?|\bwhatsapp|\breferencia|\bref\.?|\bc[oó]digo|\bn[uú]mero|\bnro\.?|#)"
    r"\s*[:#.]?\s*(?:\*+|x+)?\d[\d.,\s-]*\d",
    re.IGNORECASE,
)
# Un NIT trae dígito de verificación: «901.658.107-1». Un monto nunca termina en «-dígito».
_CON_DIGITO_VERIFICACION = re.compile(r"\d{1,3}(?:[.,]\d{3})+-\d\b")


def sin_documentos(texto: str) -> str:
    return _CON_DIGITO_VERIFICACION.sub(" ", _DOCUMENTOS.sub(" ", texto))


def extraer_monto(texto: str, estricto: bool = False, sanear: bool = True) -> float:
    if sanear:
        texto = sin_documentos(texto)
    patrones = _AMOUNT_PATTERNS[:-_CIFRAS_SUELTAS] if estricto else _AMOUNT_PATTERNS
    for patron in patrones:
        for m in patron.finditer(texto):
            crudo = m.group(1)
            n = _parse_num(crudo)
            if patron is _AMOUNT_PATTERNS[-1] and _parece_anio(crudo, n):
                continue  # un año («de 2026») no es un monto; sigue buscando otra cifra
            if estricto and n > MONTO_MAXIMO_ESTRICTO:
                continue
            if 0 < n < 1e11:
                return n
    return 0.0


def extraer_moneda(texto: str) -> str:
    if re.search(r"\bUSD\b|US\$|\bd[oó]lares?\b", texto, re.IGNORECASE):
        return "USD"
    if re.search(r"\bEUR\b|\beuros?\b", texto, re.IGNORECASE):
        return "EUR"
    return "COP"


def _bonito(nombre: str) -> str:
    """Limpia espacios y baja las MAYÚSCULAS ('JUAN VALDEZ' -> 'Juan Valdez'); lo mixto no se toca."""
    n = " ".join(nombre.strip(" -:*").split())[:40]
    return n.title() if n.isupper() else n


def extraer_concepto(asunto: str, cuerpo: str = "") -> str:
    """'Compra en Juan Valdez', 'Envío a Ana', 'Pago de servicios'... leído del asunto
    (primero) o del cuerpo. '' si no hay nada que se entienda."""
    for texto in (asunto or "", cuerpo or ""):
        for patron, prefijo in _CONCEPTOS:
            m = patron.search(texto)
            if m:
                nombre = _bonito(m.group(1))
                if nombre:
                    return f"{prefijo}{nombre}"
        m = _ASTERISCO.search(texto)  # 'BOLD*CAFE LUNA' / '*RAPPI*'
        if m:
            return f"Compra en {_bonito(m.group(1))}"
    return ""


def descripcion_sin_detalle(texto: str) -> str:
    """Respaldo claro cuando un correo bancario no dice dónde fue el movimiento. Nunca el remitente."""
    tipo = detectar_tipo(texto)
    return "Ingreso sin detalle" if tipo == "income" else "Gasto sin detalle"


def extraer_comercio(remitente: str, asunto: str, cuerpo: str = "") -> str:
    """Qué describe el movimiento: el concepto o comercio del asunto/cuerpo. Si el remitente
    es un banco y el correo no dice más, un respaldo ('Gasto sin detalle'), no el nombre del
    banco: el banco ya aparece en la tarjeta y en la cuenta."""
    concepto = extraer_concepto(asunto, cuerpo)
    if concepto:
        return concepto

    remitente_lower = (remitente or "").lower()
    for clave, nombre in _COMERCIO_MAP:
        if clave in remitente_lower:
            return nombre
    if any(clave in remitente_lower for clave, _ in _BANK_MAP):
        return descripcion_sin_detalle(f"{asunto or ''} {cuerpo or ''}")

    m = re.match(r'^"?([^"<@]+)"?\s*<', remitente or "")
    if m:
        nombre = m.group(1).strip()
        return " ".join(w.capitalize() for w in nombre.split())

    asunto_limpio = re.sub(r"^(RE|FWD|RE:FWD):\s*", "", asunto or "", flags=re.IGNORECASE).strip()
    palabras = [
        w.capitalize()
        for w in re.split(r"[\s\-|:,]+", asunto_limpio)
        if len(w) > 2 and not w.isdigit() and not w.startswith(("%", "$"))
    ]
    if palabras:
        return " ".join(palabras[:3])

    return (remitente or "").split("@")[0] or "Desconocido"


def detectar_tipo(texto: str) -> str:
    """Siempre con dirección: 'income' (entró plata) o 'expense' (salió). Nunca 'transfer':
    un traslado propio mueve saldo igual que cualquier otro movimiento y se marca aparte
    con es_posible_traslado_propio. Si el correo trae palabras de entrada y de salida, gana
    la que aparece primero; si no trae ninguna, se asume gasto."""
    ingreso = _INGRESO_RE.search(texto or "")
    salida = _EGRESO_RE.search(texto or "")
    if ingreso and (not salida or ingreso.start() <= salida.start()):
        return "income"
    return "expense"


def es_posible_traslado_propio(texto: str) -> bool:
    """El correo habla de pasar plata entre cuentas del mismo dueño (pista, no certeza)."""
    return bool(_TRANSFER_RE.search(texto or ""))


def texto_cuerpo(msg: dict, limite: int = 6000) -> str:
    """Texto plano del cuerpo de un mensaje de Gmail (format=full), sin etiquetas HTML y recortado.
    Sirve solo para encontrar el monto o el comercio cuando no caben en el fragmento (`snippet`); el
    resultado no se guarda en la base de datos (minimización de datos)."""
    import base64
    import html as _html

    trozos: list[tuple[int, str]] = []  # (prioridad, texto): 0 = texto plano, 1 = HTML

    def recorrer(parte: dict):
        if len(trozos) > 8:
            return
        tipo = (parte.get("mimeType") or "").lower()
        data = (parte.get("body") or {}).get("data")
        if data and tipo in ("text/plain", "text/html"):
            try:
                crudo = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                crudo = ""
            if tipo == "text/html":
                crudo = re.sub(r"(?is)<(script|style).*?</\1>", " ", crudo)
                crudo = re.sub(r"(?s)<[^>]+>", " ", crudo)
                crudo = _html.unescape(crudo)
            crudo = re.sub(r"\s+", " ", crudo).strip()
            if crudo:
                trozos.append((0 if tipo == "text/plain" else 1, crudo))
        for hija in parte.get("parts") or []:
            recorrer(hija)

    recorrer(msg.get("payload") or {})
    if not trozos:
        return ""
    trozos.sort(key=lambda t: t[0])
    return trozos[0][1][:limite]



# ── Fecha del movimiento ──────────────────────────────────────────────────────────────────
# El banco escribe la fecha del movimiento DENTRO del texto («el 3 de julio de 2026 a las 11:05 am»);
# el correo puede llegar horas o días después. Todo en hora de Colombia (UTC-5, sin horario de verano).
from datetime import datetime, timedelta  # noqa: E402

_DESFASE_CO = timedelta(hours=5)
_MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
          "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}
_MES_RE = r"(ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|set(?:iembre)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)"
_FECHA_PATRONES = [
    # «8 de octubre de 2026», «8 oct 2026», «8-oct-2026», «8/oct/2026»; el año puede faltar solo con «de mes»
    re.compile(r"(?<!\d)(\d{1,2})\s*(?:de\s+|[-/.\s]\s*)" + _MES_RE + r"\.?(?:\s*(?:de\s+|[-/.,\s]\s*)(\d{4}))?(?!\w)", re.IGNORECASE),
    # «08/10/2026», «8-10-2026», «08.10.2026» (día/mes/año, como se escribe en Colombia)
    re.compile(r"(?<![\d/.-])(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?![\d/.-])"),
    # «2026-10-08»
    re.compile(r"(?<![\d/.-])(\d{4})-(\d{2})-(\d{2})(?![\d/.-])"),
]
_HORA_RE = re.compile(r"(?:a\s+las\s+|hora:?\s*|a\s+la\s+)?(\d{1,2})[:.](\d{2})(?::\d{2})?\s*([ap])\.?\s?m\.?(?!\w)|"
                      r"(?:a\s+las\s+|hora:?\s*)?(?<![\d:.])([01]?\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?(?![\d:])", re.IGNORECASE)


def _sin_tildes(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))


def _hora_cerca(texto: str, fin: int, ini: int) -> tuple[int, int] | None:
    """Hora escrita pegada a la fecha (después, o antes con «hora:»). None si no hay."""
    for trozo in (texto[fin:fin + 45], texto[max(0, ini - 22):ini]):
        m = _HORA_RE.search(trozo)
        if not m:
            continue
        if m.group(1):
            h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
            if not 1 <= h <= 12 or mi > 59:
                continue
            return (h % 12) + (12 if ap == "p" else 0), mi
        return int(m.group(4)), int(m.group(5))
    return None


def buscar_fecha_en_texto(texto: str, recibido_en: datetime | None = None, ahora: datetime | None = None) -> datetime | None:
    """Fecha (y hora si la trae) que el banco escribió en el texto, en hora de Colombia ('naive').
    None si no hay ninguna, si hay dos distintas (ambigüedad) o si no es creíble: futura, de hace
    más de 5 años o posterior al día en que llegó el correo. Sin hora, queda a las 00:00."""
    texto = _sin_tildes(texto or "")
    recibido_co = recibido_en - _DESFASE_CO if recibido_en else None
    ahora_co_ = ahora or (datetime.utcnow() - _DESFASE_CO)
    encontradas: dict[datetime, bool] = {}  # fecha -> trae hora
    for i, patron in enumerate(_FECHA_PATRONES):
        for m in patron.finditer(texto):
            try:
                if i == 0:
                    dia, mes = int(m.group(1)), _MESES[m.group(2).lower()[:3]]
                    anio = int(m.group(3)) if m.group(3) else None
                    if anio is None:  # «el 3 de julio»: el año más reciente que no quede en el futuro
                        base = recibido_co or ahora_co_
                        anio = base.year
                        if datetime(anio, mes, dia) > base + timedelta(days=1):
                            anio -= 1
                elif i == 1:
                    dia, mes, anio = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    anio, mes, dia = int(m.group(1)), int(m.group(2)), int(m.group(3))
                fecha = datetime(anio, mes, dia)
            except (ValueError, KeyError):
                continue
            hora = _hora_cerca(texto, m.end(), m.start())
            if hora:
                fecha = fecha.replace(hour=hora[0], minute=hora[1])
            if fecha > ahora_co_ + timedelta(days=1) or fecha < ahora_co_ - timedelta(days=5 * 365):
                continue
            if recibido_co and fecha.date() > (recibido_co + timedelta(days=1)).date():
                continue
            encontradas[fecha] = hora is not None
    if not encontradas:
        return None
    if len({f.date() for f in encontradas}) > 1:
        return None  # dos fechas distintas en el texto: no se adivina, vale la del correo
    # Misma fecha repetida: gana la que trae hora.
    return max(encontradas, key=lambda f: (encontradas[f], f))


def extraer_fecha_movimiento(texto: str, recibido_en: datetime | None = None) -> datetime | None:
    """Fecha del movimiento en UTC ('naive', igual que `recibido_en`): la del texto del correo si
    existe y es creíble; si no, la fecha de recepción (que puede ser None)."""
    co = buscar_fecha_en_texto(texto, recibido_en)
    return co + _DESFASE_CO if co else recibido_en


def fecha_movimiento_info(correo) -> dict:
    """De un CorreoGasto: {fecha (hora Colombia, naive), con_hora, del_texto}. Usa la columna
    `fecha_movimiento` si está; si no (correos viejos), la busca al vuelo en asunto+fragmento; y si
    tampoco, la de recepción (o la de creación)."""
    guardada = getattr(correo, "fecha_movimiento", None)
    if guardada:
        co = guardada - _DESFASE_CO
        return {"fecha": co, "con_hora": (co.hour, co.minute) != (0, 0), "del_texto": True}
    co = buscar_fecha_en_texto(f"{correo.asunto or ''} {correo.snippet or ''}", correo.recibido_en)
    if co:
        return {"fecha": co, "con_hora": (co.hour, co.minute) != (0, 0), "del_texto": True}
    base = correo.recibido_en or correo.creado_en
    return {"fecha": base - _DESFASE_CO if base else None, "con_hora": bool(correo.recibido_en), "del_texto": False}
