"""Notificaciones del teléfono (Android) -> movimiento «por confirmar».

La app de Android lee las notificaciones de Wallet y de los bancos y manda el texto CRUDO a
`POST /movimientos/rapido-notificacion`. El análisis vive aquí, en el servidor, para poder mejorarlo
(un banco que cambia su texto, una app nueva) sin que nadie reinstale nada. Reutiliza los lectores de correos
bancarios (`gmail_extract`: monto, dirección, comercio) y les suma los formatos propios de una notificación.

Es una función PURA (sin base de datos): fácil de probar con textos inventados. Nunca adivina: si la
notificación no parece un movimiento de dinero (códigos de seguridad, promociones, avisos sin monto), devuelve None.
"""
import re
from dataclasses import dataclass

from app import gmail_extract as ge
from app.wallet import parse_monto_co

# Apps cuyas notificaciones se leen. El teléfono pide esta lista al servidor (GET /movimientos/notificaciones-apps):
# agregar una app aquí no requiere reinstalar el APK. `clase`: 'wallet' (la notificación trae comercio y tarjeta)
# o 'banco' (el texto es del banco; la cuenta se busca por el nombre del banco).
# OJO: los nombres de paquete de bancos se confirman con un teléfono real; un paquete que no esté acá igual se
# procesa si el texto parece un movimiento y el teléfono decide enviarlo.
APPS: dict[str, tuple[str, str]] = {
    "com.google.android.apps.walletnfcrel": ("Google Wallet", "wallet"),
    "com.google.android.apps.nbu.paisa.user": ("Google Pay", "wallet"),
    "com.nequi.MobileApp": ("Nequi", "banco"),
    "com.nu.production": ("Nu", "banco"),
    "co.com.nu.android": ("Nu", "banco"),
    "com.todo1.mobile": ("Bancolombia", "banco"),
    "com.bancolombia.alamano": ("Bancolombia", "banco"),
    "com.davivienda.daviplataapp": ("Daviplata", "banco"),
    "com.davivienda.mobile": ("Davivienda", "banco"),
}

# iOS (Atajos) no manda un paquete de Android sino el NOMBRE de la app que puso quien armó el atajo.
ALIAS_IOS: dict[str, tuple[str, str]] = {
    "nequi": ("Nequi", "banco"), "nu": ("Nu", "banco"), "bancolombia": ("Bancolombia", "banco"),
    "davivienda": ("Davivienda", "banco"), "daviplata": ("Daviplata", "banco"),
}

# --- Lectura general, para cualquier banco o billetera (iPhone y Android) ---------------------------------------
# Nequi, textos reales vistos en iPhone:
#  «Envío» / «DANIEL PARRADO te envió 1, ¡lo mejor!»  -> te llegó plata (trae monto y quién; a veces sin «$»).
#  «Tu plata llegó con éxito» / «Envío exitoso, la plata ya está en el Nequi destino…» -> TÚ enviaste plata,
#  pero el aviso NO trae monto ni a quién. Otros bancos dirán cosas parecidas, por eso se lee por VERBOS y no
#  por banco; lo que no se entiende se le pregunta a la persona (ver `pide_monto` y `Notificacion.tipo_incierto`).
_ENTRA = re.compile(
    r"te\s+(?:envi[oó]|enviaron|lleg[oó]|llegaron|consign\w+|deposit\w+|transfiri\w+|abon\w+|pag[oó]|pagaron|"
    r"mand[oó]|giraron|gir[oó])|recibiste|has\s+recibido|te\s+han\s+(?:enviado|transferido|consignado|pagado|abonado)|"
    r"transferencia\s+recibida|dep[oó]sito\s+recibido|env[ií]o\s+recibido|abono\s+(?:a|en)\s+tu|pix\s+recebido|n[oó]mina",
    re.IGNORECASE,
)
_SALE = re.compile(
    r"enviaste|transferiste|pagaste|compraste|retiraste|giraste|recargaste|"
    r"compra\s+(?:aprobada|exitosa)|pago\s+(?:exitoso|aprobado|realizado)|d[eé]bito|se\s+(?:debit|cobr)|"
    # Comprobantes que el atajo lee de una captura de pantalla (Nu no avisa al enviar plata): con monto, salió plata
    r"transferencia\s+exitosa|env[ií]o\s+exitoso|env[ií]o\s+realizado|comprobante\s+de\s+(?:transferencia|env[ií]o|pago)|"
    r"enviado\s+a|le\s+enviaste",
    re.IGNORECASE,
)
# Aviso de que SALIÓ plata pero sin cifra: «envío exitoso», «transferencia exitosa», «tu plata llegó con éxito»...
_SIN_CIFRA = re.compile(
    r"plata\s+lleg[oó]\s+con\s+[eé]xito|env[ií]o\s+exitoso|transferencia\s+exitosa|pago\s+exitoso|"
    r"enviaste\s+(?:la\s+)?(?:plata|dinero)|ya\s+le\s+lleg[oó]",
    re.IGNORECASE,
)
# «X te envió 1» sin signo de pesos: el número va pegado al verbo
_CIFRA_TRAS_VERBO = re.compile(
    r"(?:envi[oó]|enviaron|recibiste|consign\w+|deposit\w+|transfiri\w+|abon\w+|pag[oó]|enviaste|pagaste|transferiste)"
    r"\s+\$?\s*(\d[\d.,]*\d|\d)(?![\d.,]*\s*(?:%|d[ií]as|veces))",
    re.IGNORECASE,
)
# «... Para LAURA GOMEZ Banco ...»: en un comprobante el destinatario va en mayúsculas tras «Para»
_PARA_QUIEN = re.compile(r"\bPara\s+(?P<q>[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,3})\b")
_QUIEN = re.compile(r"(?P<q>[^.\n!¡]{2,60}?)\s+te\s+(?:envi[oó]|enviaron|mand[oó]|transfiri\w+|consign\w+|pag[oó])", re.IGNORECASE)


def _direccion(cuerpo: str) -> str | None:
    """'income' | 'expense' | None si el texto no dice hacia dónde fue la plata. Gana la señal que aparece primero."""
    e, s = _ENTRA.search(cuerpo), _SALE.search(cuerpo)
    if e and (not s or e.start() <= s.start()):
        return "income"
    return "expense" if s else None


def _monto_sin_signo(cuerpo: str) -> float:
    m = _CIFRA_TRAS_VERBO.search(cuerpo)
    if not m:
        return 0.0
    try:
        return parse_monto_co(m.group(1))
    except ValueError:
        return 0.0


def _quien(cuerpo: str) -> str:
    m = _QUIEN.search(cuerpo)
    return _limpiar(m.group("q").split(". ")[-1]) if m else ""


# ---- Comprobantes y detalles de movimiento leídos de un pantallazo (formatos vistos en Nu y Nequi) ----------------
# Palabras que NO son parte de un nombre: etiquetas del comprobante que siguen al nombre («Entidad», «Llave», «¿Cuánto?»...).
_ETIQUETAS = {"nombre", "entidad", "llave", "banco", "numero", "fecha", "cuanto", "referencia", "documento", "cuenta",
              "monto", "total", "via", "tipo", "comprobante", "concepto", "valor", "impuesto", "disponible", "algun",
              "donde", "para", "compartir", "descargar", "detalle"}
_PARTICULAS = {"de", "del", "la", "las", "los", "y", "da", "dos"}
_NOMBRE_ANTES_DEL_MONTO = re.compile(r"([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,4})\s+\$")
_MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}
_FECHA = re.compile(
    r"(\d{1,2})\s*(?:de\s+)?(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[a-z]*\.?\s*(?:de\s+)?(\d{4})"
    r"(?:\s*(?:-|,|a\s+las?)?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(a\.?\s*m\.?|p\.?\s*m\.?)?)?",
    re.IGNORECASE,
)
_ID_COMPROBANTE = re.compile(r"(?:ID\s+MOL\)?|Referencia|Comprobante\s+No\.?)\s*[:\s]\s*([A-Z0-9]{6,})")
# «Producto destino  Nequi  3143082864»: no trae nombre, solo a qué producto se envió (se muestra con los últimos 4 dígitos)
_PRODUCTO_DESTINO = re.compile(r"Producto\s+destino\s+(?P<prod>[A-Za-zÁÉÍÓÚáéíóúñÑ]+(?:\s+[A-Za-zÁÉÍÓÚáéíóúñÑ]+){0,3}?)\s+[*•·]?\s*(?P<num>\d[\d\s]{3,})")
# Valor que el comprobante rotula, para no confundirlo con otra cifra (impuesto, saldo, llave...)
_MONTO_ETIQUETADO = re.compile(
    r"(?:valor\s+de\s+la\s+transferencia|monto\s+total|valor\s+total|cu[aá]nto\??)\s*:?\s*\$?\s*(\d[\d.,]*\d|\d)", re.IGNORECASE)
# Pantalla de una compra con tarjeta (detalle de Apple Pay / Wallet, aviso del banco): «••1234», «Apple Pay»
_TARJETA_PANTALLA = re.compile(r"[•·*]{2,}\s*\d{4}|apple\s+pay|\bwallet\b", re.IGNORECASE)
# Palabras que delatan que unas mayúsculas NO son un nombre de persona
_NO_ES_NOMBRE = {"compra", "transferencia", "pago", "aprobada", "aprobado", "exitosa", "exitoso", "monto", "total", "valor",
                 "comprobante", "envio", "recibido", "retiro", "saldo", "cuenta", "tarjeta", "debito", "credito"}


def _monto_etiquetado(cuerpo: str) -> float:
    m = _MONTO_ETIQUETADO.search(cuerpo)
    if not m:
        return 0.0
    try:
        return parse_monto_co(m.group(1))
    except ValueError:
        return 0.0


def _tomar_nombre(resto: str) -> str:
    """Palabras seguidas con aspecto de nombre propio (mayúscula inicial; «de», «la»... dentro del nombre), hasta que
    aparece una etiqueta del comprobante o algo que no es una palabra. Pide al menos dos palabras."""
    palabras: list[str] = []
    for tok in resto.split():
        limpio = tok.strip(".,:;()")
        if not limpio or not limpio[0].isalpha():
            break
        base = _sin_tildes(limpio)
        if base in _ETIQUETAS and (palabras or base != "nombre"):
            break
        if base == "nombre" and not palabras:
            continue  # «Para Nombre YIDYEH SILVA»: «Nombre» es la etiqueta
        if limpio[0].isupper() or (base in _PARTICULAS and palabras):
            palabras.append(limpio)
        else:
            break
        if len(palabras) >= 6:
            break
    while palabras and _sin_tildes(palabras[-1]) in _PARTICULAS:
        palabras.pop()
    return " ".join(palabras) if len(palabras) >= 2 else ""


def _destinatario(cuerpo: str) -> str:
    """A quién se le envió, de un comprobante: «Para <nombre>» (Nu comprobante, Nequi) o el nombre en mayúsculas que va
    pegado al valor («JORGE PEREZ $23.000», detalle de Nu). '' si no se encuentra."""
    m = re.search(r"\bPara\s+(.{0,140})", cuerpo)
    if m:
        nombre = _tomar_nombre(m.group(1))
        if nombre:
            return _limpiar(nombre)
    m = _NOMBRE_ANTES_DEL_MONTO.search(cuerpo)
    if m and not any(_sin_tildes(p) in _NO_ES_NOMBRE for p in m.group(1).split()):
        return _limpiar(m.group(1))
    return ""


def _remitente(cuerpo: str) -> str:
    """Quién te envió, de un comprobante de ingreso: «Recibiste de <nombre>» (Nu) o el campo «De <nombre>» (Nequi)."""
    m = re.search(r"\b[Rr]ecibiste\s+de\s+(.{0,140})", cuerpo)
    if m:
        nombre = _tomar_nombre(m.group(1))
        if nombre:
            return _limpiar(nombre)
    m = re.search(r"\bDe\s+(.{0,140})", cuerpo)  # «De» con mayúscula = rótulo del campo, no una frase
    if m:
        nombre = _tomar_nombre(m.group(1))
        if nombre:
            return _limpiar(nombre)
    return ""


def _producto_destino(cuerpo: str) -> str:
    """«Envío a Nequi ·2864» a partir de «Producto destino Nequi 3143082864» (comprobantes que no traen el nombre)."""
    m = _PRODUCTO_DESTINO.search(cuerpo)
    if not m:
        return ""
    digitos = re.sub(r"\D", "", m.group("num"))
    return f"{_limpiar(m.group('prod'))} ·{digitos[-4:]}" if len(digitos) >= 4 else ""


def _fecha_en_texto(cuerpo: str) -> str | None:
    """Fecha y hora que trae el comprobante («05 NOV 2026 - 20:08:29», «6 de noviembre de 2026, 12:52», «a las 10:52 p. m.»)
    en ISO. None si el texto no trae una fecha reconocible (un aviso de notificación no la trae)."""
    m = _FECHA.search(_sin_tildes(cuerpo))
    if not m:
        return None
    dia, mes, anio = int(m.group(1)), _MESES[m.group(2).lower()], int(m.group(3))
    hora, minuto, segundo = int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0)
    meridiano = (m.group(7) or "").replace(".", "").replace(" ", "").lower()
    if meridiano == "pm" and hora < 12:
        hora += 12
    elif meridiano == "am" and hora == 12:
        hora = 0
    if not (1 <= dia <= 31 and 1990 <= anio <= 2100 and hora < 24 and minuto < 60 and segundo < 60):
        return None
    return f"{anio:04d}-{mes:02d}-{dia:02d}T{hora:02d}:{minuto:02d}:{segundo:02d}"


def _id_comprobante(cuerpo: str) -> str | None:
    """Número único que el banco imprime en el comprobante (Nu: ID MOL, Nequi: Referencia). Sirve para que repetir el gesto
    sobre el MISMO comprobante nunca cree otro movimiento."""
    m = _ID_COMPROBANTE.search(cuerpo)
    return m.group(1) if m else None


def pide_monto(paquete: str, titulo: str, texto: str) -> bool:
    """Salió plata pero el aviso no trae cifra (Nequi: «Tu plata llegó con éxito»): el atajo de iPhone le pregunta
    a la persona cuánto fue y para qué. Cualquier banco que avise así queda cubierto."""
    cuerpo = f"{titulo}. {texto}"
    if _RUIDO.search(cuerpo) or ge.extraer_monto(cuerpo) or _monto_sin_signo(cuerpo) or _ENTRA.search(cuerpo):
        return False
    return bool(_SIN_CIFRA.search(cuerpo))


# Notificaciones que NUNCA son un movimiento: códigos, claves, promociones, avisos de seguridad.
_RUIDO = re.compile(
    r"c[oó]digo|clave\s+din[aá]mica|\botp\b|\btoken\b|no\s+(?:lo\s+)?compartas|verificaci[oó]n|inicio\s+de\s+sesi[oó]n|"
    r"nuevo\s+dispositivo|promoci[oó]n|\boferta|descuento|sorteo|\bgana\b|te\s+invitamos|aprovecha|cashback\s+disponible|"
    r"solicitud\s+(?:de|aprobada)|actualiza\s+tu\s+app|recuerda\s+pagar|fecha\s+l[ií]mite",
    re.IGNORECASE,
)

_MONTO = r"\$\s*[\d.,]+"
# «$20.000 COP a JUMBO» (título típico de Google Wallet)
_TITULO_WALLET = re.compile(rf"^\s*(?:{_MONTO}|[\d.,]+)\s*(?:COP|USD)?\s+(?:a|en)\s+(.+?)\s*$", re.IGNORECASE)
# «Pagaste $20.000 en JUMBO con ...» / «Compra aprobada por $45.900 en Mercado Libre»
_PAGO_EN = re.compile(
    rf"(?:pagaste|compraste|pago|compra|cobro|d[eé]bito)[^$]*?{_MONTO}\s*(?:COP)?\s+(?:en|a)\s+(?P<c>[^.\n]+?)"
    rf"(?=\s+(?:con|usando|desde|el\s+\d|a\s+las)\b|[.\n]|$)",
    re.IGNORECASE,
)
# «... Visa ••1234 en Jumbo Calle 80»: el comercio queda al final del texto
_EN_FINAL = re.compile(r"\b(?:en|a)\s+(?P<c>[^.\n•·*\d][^.\n•·*]{2,60}?)\s*$", re.IGNORECASE)
_NOMBRES_DE_APP = {"google", "wallet", "google wallet", "google pay", "pagaste", "compraste"}
_ULT4 = re.compile(r"(?:\*+|•+|·+|\.{2,}|terminad[ao]\s+en\s*|final\s+)\s*(?P<ult>\d{4})", re.IGNORECASE)
_MARCA = re.compile(r"visa|master\s?card|amex|american express", re.IGNORECASE)


@dataclass(frozen=True)
class Notificacion:
    monto: float
    tipo: str  # 'income' | 'expense'
    comercio: str  # nombre ya limpio (lo que se muestra como descripción)
    clase: str  # 'wallet' | 'banco'
    fuente: str  # 'google_pay' | 'notificacion'
    app: str | None  # nombre de la app/banco, si se conoce
    tarjeta: str | None  # «Visa 1234» para que Wallet mapee la cuenta por su alias
    traslado_propio: bool
    fecha: str | None = None  # la que trae el comprobante (ISO); None en un aviso
    id_externo: str | None = None  # número único del comprobante (Nu: ID MOL, Nequi: Referencia)
    tipo_incierto: bool = False  # hay monto pero el texto no dice si entró o salió: iPhone pregunta, Android asume gasto


def _limpiar(c: str) -> str:
    c = re.sub(r"\s+", " ", c or "").strip(" .,-:;")
    return c.title() if c.isupper() else c


def _tarjeta(texto: str) -> str | None:
    m = _ULT4.search(texto or "")
    if not m:
        return None
    # La marca (Visa, Mastercard...) suele estar justo antes de los últimos 4 dígitos
    cerca = texto[max(0, m.start() - 25): m.end()]
    marca = _MARCA.search(cerca)
    return f"{marca.group(0).title() if marca else ''} {m.group('ult')}".strip()


def es_ruido(titulo: str, texto: str) -> bool:
    """Códigos, promociones y avisos de seguridad: nunca son un movimiento ni merecen contarse como «no entendido»."""
    return bool(_RUIDO.search(f"{titulo or ''}. {texto or ''}"))


def nombre_app(paquete: str) -> str:
    """Nombre legible de la app: de la lista de Android, del alias de iPhone o, si es una app nueva, el texto tal cual."""
    p = (paquete or "").strip()
    return (APPS.get(p) or ALIAS_IOS.get(p.lower()) or (p[:40], ""))[0]


def banco_de_cuenta(nombre_cuenta: str) -> str | None:
    """Banco/billetera que el atajo sabe leer según el nombre de la cuenta («Nu Colombia» -> Nu), o None."""
    palabras = set(re.findall(r"[a-z0-9]+", _sin_tildes(nombre_cuenta)))
    for clave, (nombre, _clase) in ALIAS_IOS.items():
        if clave in palabras:
            return nombre
    return None


def _sin_tildes(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")


def es_ios(paquete: str) -> bool:
    """El atajo de iPhone manda el NOMBRE de la app (Nequi, Nu...), no un paquete de Android (com.x.y)."""
    p = (paquete or "").strip()
    return bool(p) and p not in APPS and "." not in p


def interpretar(paquete: str, titulo: str, texto: str) -> Notificacion | None:
    """Devuelve el movimiento que insinúa la notificación, o None si no parece uno."""
    titulo, texto = (titulo or "").strip(), (texto or "").strip()
    cuerpo = f"{titulo}. {texto}".strip(". ")
    if len(cuerpo) < 8 or _RUIDO.search(cuerpo):
        return None
    app, clase = APPS.get(paquete or "") or ALIAS_IOS.get((paquete or "").strip().lower(), (None, "banco"))
    monto = _monto_etiquetado(cuerpo) or ge.extraer_monto(cuerpo) or _monto_sin_signo(cuerpo)
    if not monto or monto <= 0:
        return None
    direccion = _direccion(cuerpo)
    es_tarjeta = bool(_TARJETA_PANTALLA.search(cuerpo))
    if direccion is None and es_tarjeta and not _ENTRA.search(cuerpo):
        direccion = "expense"  # una compra con tarjeta o Apple Pay siempre es un gasto: no hace falta preguntar
    tipo = direccion or ge.detectar_tipo(cuerpo)
    incierto = direccion is None and not (ge._INGRESO_RE.search(cuerpo) or ge._EGRESO_RE.search(cuerpo))

    comercio = ""
    if tipo == "income" and direccion == "income":
        quien = _quien(cuerpo) or _remitente(cuerpo)  # «ANA PEREZ te envió $45.000» / «Recibiste de Ana» -> «De Ana Perez»
        if quien:
            comercio = f"De {quien}"
    m = _TITULO_WALLET.match(titulo)
    if m and not comercio:  # título de Wallet: «$20.000 COP a JUMBO»
        comercio = _limpiar(m.group(1))
        clase = "wallet"
    if not comercio and tipo == "expense":  # comprobante de envío: «Para YIDYEH SILVA» -> «Envío a Yidyeh Silva»
        quien_envio = _destinatario(cuerpo)
        if quien_envio:
            comercio = quien_envio if es_tarjeta else f"Envío a {quien_envio}"
        else:
            producto = _producto_destino(cuerpo)
            if producto:
                comercio = f"Envío a {producto}"
    if not comercio:
        # Primero el lector de correos bancarios («Envío a Ana», «Recibido de Luis», «Compra en Éxito»)...
        c0 = ge.extraer_comercio(app or ("" if (paquete or "").strip().lower() in ("auto", "pantalla") else paquete or ""), titulo, texto)
        if c0 and not c0.lower().endswith("sin detalle") and c0.lower() not in _NOMBRES_DE_APP and c0.lower() != (app or "").lower():
            comercio = c0
    if not comercio:  # ...y si no dice nada concreto, los formatos propios de una notificación
        m = _PAGO_EN.search(cuerpo) or _EN_FINAL.search(texto)
        if m:
            comercio = _limpiar(m.group("c"))
    if not comercio:
        comercio = "Plata recibida" if tipo == "income" else "Movimiento sin detalle"

    es_wallet = clase == "wallet"
    return Notificacion(
        monto=float(monto),
        tipo=tipo,
        comercio=comercio[:150],
        clase=clase,
        fuente="google_pay" if es_wallet else "notificacion",
        app=app,
        tarjeta=_tarjeta(cuerpo),
        traslado_propio=ge.es_posible_traslado_propio(cuerpo),
        fecha=_fecha_en_texto(cuerpo),
        id_externo=_id_comprobante(cuerpo),
        tipo_incierto=incierto,
    )
