"""Huella de comercio: la parte de una descripción bancaria que identifica
DÓNDE se gastó, sin el ruido que cambia en cada extracto.

    'PAGO EN VENTO COLIVING 0105'      -> 'vento coliving'
    'COMPRA VENTO COLIVING BOGOTA'     -> 'vento coliving'

Es la única función que se usa para guardar y para buscar reglas aprendidas:
así la regla que el usuario crea con un movimiento sirve para cualquier otra
descripción del mismo comercio. No toca la base de datos (es pura y barata).
"""
import re
import unicodedata
from functools import lru_cache

# Palabras genéricas de la operación bancaria: se quitan SOLO al inicio.
_PREFIJOS = {
    "pago", "pagos", "compra", "compras", "en", "a", "de", "del", "por", "desde", "pse",
    "abono", "retiro", "transferencia", "transf", "trf", "tarjeta", "tc", "td", "debito",
    "credito", "internacional", "nacional", "cargo", "consignacion", "envio", "giro",
    "recibiste", "enviaste", "cuota", "avance", "pos", "app", "nequi", "daviplata",
    "bancolombia", "davivienda", "bre", "b", "movimiento", "mov",
    # pasarela de pagos ('BOLD*Cafe Luna') y 'EDS' (estación de servicio): el comercio es lo que sigue
    "bold", "eds", "qr", "recibi", "envio",
}
# Se cortan en cuanto aparecen: lo que sigue es detalle de la operación.
_CORTES = {"con", "terminacion", "term", "ref", "referencia", "nro", "numero", "cuenta", "cta", "tarjeta", "autorizacion", "aut", "cod", "codigo"}
# Se quitan en cualquier parte: forma jurídica, país y ciudades comunes.
_RUIDO = {
    "sas", "sa", "ltda", "ltd", "inc", "llc", "cia", "cía", "scs", "bog", "bta", "med", "cal", "co", "col",
    "com", "www", "http", "https", "cop", "usd", "dc", "colombia", "bogota", "medellin", "cali",
    "barranquilla", "cartagena", "bucaramanga", "pereira", "manizales", "cucuta", "ibague",
    "armenia", "villavicencio", "neiva", "pasto", "monteria", "valledupar", "popayan", "tunja",
    "envigado", "itagui", "sabaneta", "bello", "soacha", "chia", "cajica", "zipaquira", "rionegro",
    "floridablanca", "giron", "piedecuesta", "dosquebradas", "palmira", "tulua", "buenaventura",
    "amzn", "esp", "cundinamarca", "antioquia", "valle", "atlantico", "santander", "sucursal", "suc",
}
_RE_JURIDICA = re.compile(r"\b(s\s*\.\s*a\s*\.\s*s|s\s*\.\s*a|s\s*\.\s*en\s*c|e\s*\.\s*s\s*\.\s*p|ltda)\b\.?", re.IGNORECASE)
_RE_FECHA = re.compile(r"\b\d{1,4}[/\-.]\d{1,2}([/\-.]\d{1,4})?\b")
MAX_PALABRAS = 3
_RE_CODIGO_TIENDA = re.compile(r"^[a-z]{1,2}\d{1,3}$")
_COLA = {"de", "del", "la", "el", "los", "las", "en", "y", "e", "a", "al", "por", "para", "and"}

# Una huella con SOLO estas palabras (o muy corta) abarcaría demasiado.
PALABRAS_VACIAS = {
    "otros", "otro", "pago", "compra", "transferencia", "banco", "tienda", "servicio", "servicios",
    "cliente", "gasto", "ingreso", "cuota", "valor", "total", "movimiento", "persona", "efectivo",
    "app", "web", "online", "internet", "el", "la", "los", "las", "una", "uno", "mi", "tu",
    "comercio", "tarjeta", "cuenta", "cobro", "debito", "credito", "abono", "retiro", "pse",
    "nomina", "comision", "intereses", "iva", "suscripcion", "mensual", "anual",
}


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=16384)
def clave_comercio(descripcion: str | None) -> str:
    """Huella normalizada del comercio. Devuelve '' si no queda nada útil."""
    if not descripcion:
        return ""
    t = _sin_tildes(str(descripcion).lower())
    t = _RE_JURIDICA.sub(" ", t)
    t = _RE_FECHA.sub(" ", t)
    t = re.sub(r"[''`´]", "", t)  # "pan pa' ya" -> "pan pa ya"
    t = re.sub(r"[^a-z0-9]+", " ", t)
    tokens = t.split()

    # corta el detalle de la operación (solo si ya hay nombre antes)
    limpios: list[str] = []
    inicio = True
    for tok in tokens:
        if inicio and tok in _PREFIJOS:
            continue
        inicio = False
        if tok in _CORTES and limpios:
            break
        if tok in _CORTES:
            continue
        limpios.append(tok)

    resultado = []
    for tok in limpios:
        if tok in _RUIDO:
            continue
        if tok.isdigit():
            continue
        if any(ch.isdigit() for ch in tok) and len(tok) > 3:  # referencias/códigos; se conserva 'd1'
            continue
        if _RE_CODIGO_TIENDA.match(tok) and tok != "d1":  # 'r46', 'h11': código del local, no del comercio
            continue
        if len(tok) == 1:  # restos de siglas ('s', 'a')
            continue
        resultado.append(tok)
    while resultado and resultado[-1] in _COLA:
        resultado.pop()
    while resultado and resultado[0] in _COLA:
        resultado.pop(0)
    return " ".join(resultado[:MAX_PALABRAS])


def es_huella_peligrosa(huella: str) -> str | None:
    """Motivo por el que una huella es demasiado amplia para guardarse como
    regla sin que el usuario lo confirme; None si es segura."""
    h = (huella or "").strip()
    if not h:
        return "No se reconoció un comercio en la descripción"
    palabras = h.split()
    if all(p in PALABRAS_VACIAS for p in palabras):
        return f"«{h}» es una palabra muy genérica y afectaría muchos movimientos"
    if len(palabras) == 1 and len(palabras[0]) < 4:
        return f"«{h}» es demasiado corta y podría coincidir con muchos comercios"
    return None


def huella_en_descripcion(huella: str, descripcion: str) -> bool:
    """¿La descripción es de este comercio? Igual a la huella, o la contiene
    como palabras completas ('uber' dentro de 'uber trip')."""
    if not huella:
        return False
    clave = clave_comercio(descripcion)
    if not clave:
        return False
    if clave == huella:
        return True
    return f" {huella} " in f" {clave} "
