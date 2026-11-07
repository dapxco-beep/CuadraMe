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
    r"transferencia\s+recibida|dep[oó]sito\s+recibido|abono\s+(?:a|en)\s+tu|pix\s+recebido|n[oó]mina",
    re.IGNORECASE,
)
_SALE = re.compile(
    r"enviaste|transferiste|pagaste|compraste|retiraste|giraste|recargaste|"
    r"compra\s+(?:aprobada|exitosa)|pago\s+(?:exitoso|aprobado|realizado)|d[eé]bito|se\s+(?:debit|cobr)|"
    # Comprobantes que el atajo lee de una captura de pantalla (Nu no avisa al enviar plata): con monto, salió plata
    r"transferencia\s+exitosa|env[ií]o\s+exitoso|comprobante\s+de\s+(?:transferencia|env[ií]o|pago)|enviado\s+a|le\s+enviaste",
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
    monto = ge.extraer_monto(cuerpo) or _monto_sin_signo(cuerpo)
    if not monto or monto <= 0:
        return None
    direccion = _direccion(cuerpo)
    tipo = direccion or ge.detectar_tipo(cuerpo)
    incierto = direccion is None and not (ge._INGRESO_RE.search(cuerpo) or ge._EGRESO_RE.search(cuerpo))

    comercio = ""
    if tipo == "income" and direccion == "income":
        quien = _quien(cuerpo)  # «ANA PEREZ te envió $45.000» -> «De Ana Perez»
        if quien:
            comercio = f"De {quien}"
    m = _TITULO_WALLET.match(titulo)
    if m and not comercio:  # título de Wallet: «$20.000 COP a JUMBO»
        comercio = _limpiar(m.group(1))
        clase = "wallet"
    if not comercio:
        # Primero el lector de correos bancarios («Envío a Ana», «Recibido de Luis», «Compra en Éxito»)...
        c0 = ge.extraer_comercio(app or paquete or "", titulo, texto)
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
        tipo_incierto=incierto,
    )
