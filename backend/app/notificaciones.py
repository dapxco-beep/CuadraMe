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


def interpretar(paquete: str, titulo: str, texto: str) -> Notificacion | None:
    """Devuelve el movimiento que insinúa la notificación, o None si no parece uno."""
    titulo, texto = (titulo or "").strip(), (texto or "").strip()
    cuerpo = f"{titulo}. {texto}".strip(". ")
    if len(cuerpo) < 8 or _RUIDO.search(cuerpo):
        return None
    app, clase = APPS.get(paquete or "", (None, "banco"))
    monto = ge.extraer_monto(cuerpo)
    if not monto or monto <= 0:
        return None
    tipo = ge.detectar_tipo(cuerpo)

    comercio = ""
    m = _TITULO_WALLET.match(titulo)
    if m:  # título de Wallet: «$20.000 COP a JUMBO»
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
        comercio = "Movimiento sin detalle"

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
    )
