"""
Extracción de monto/moneda/comercio desde el texto de un correo bancario.
Patrones regex migrados de extractAmount_/extractCurrency_/extractMerchant_
en Código.js (Apps Script), probados contra bancos y comercios colombianos.
"""
import re

_AMOUNT_PATTERNS = [
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
    # Comercios y servicios frecuentes (no bancarios)
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

_SUBJECT_PATTERNS = [
    re.compile(r"\*([A-Z][A-Z0-9 ]{2,25})\*"),
    re.compile(r"(?:compra\s+en|pago\s+(?:en|a)|establecimiento[:\s]+)([A-Za-zÀ-ú][^,\n.]{2,30})", re.IGNORECASE),
    re.compile(r"(?:recibo\s+de|factura\s+de)[:\s]+([A-Za-zÀ-ú][^,\n.]{2,30})", re.IGNORECASE),
]

_INGRESO_RE = re.compile(r"recibiste|te enviaron|consignaron|abono|dep[oó]sito", re.IGNORECASE)
_TRANSFER_RE = re.compile(r"transferencia\s+entre|transferiste a tu|traslado entre cuentas", re.IGNORECASE)


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


def extraer_monto(texto: str) -> float:
    for patron in _AMOUNT_PATTERNS:
        m = patron.search(texto)
        if m:
            n = _parse_num(m.group(1))
            if 0 < n < 1e11:
                return n
    return 0.0


def extraer_moneda(texto: str) -> str:
    if re.search(r"\bUSD\b|US\$|\bd[oó]lares?\b", texto, re.IGNORECASE):
        return "USD"
    if re.search(r"\bEUR\b|\beuros?\b", texto, re.IGNORECASE):
        return "EUR"
    return "COP"


def extraer_comercio(remitente: str, asunto: str) -> str:
    remitente_lower = (remitente or "").lower()
    for clave, nombre in _BANK_MAP:
        if clave in remitente_lower:
            return nombre

    for patron in _SUBJECT_PATTERNS:
        m = patron.search(asunto or "")
        if m:
            return " ".join(m.group(1).strip().split())[:40]

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
    if _TRANSFER_RE.search(texto):
        return "transfer"
    if _INGRESO_RE.search(texto):
        return "income"
    return "expense"
