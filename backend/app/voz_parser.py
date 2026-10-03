"""
Interpreta frases habladas en español colombiano ("gasté 20 mil en el almuerzo",
"me pagaron 300 mil de sueldo") para registrar movimientos por voz/Siri sin
necesitar IA — solo patrones de texto, igual que ya se hace con notificaciones
bancarias en comercios_conocidos.py. Casos que no logra interpretar devuelven
None, para que el llamador pida confirmación en vez de adivinar mal.
"""
import re
import unicodedata

PALABRAS_INGRESO = {
    "recibi", "recibí", "me pagaron", "me consignaron", "me depositaron",
    "cobre", "cobré", "gane", "gané", "entro", "entró", "ingreso", "ingresó",
    "me dieron", "me llego", "me llegó",
}
PALABRAS_GASTO = {
    "gaste", "gasté", "pague", "pagué", "compre", "compré", "me gaste",
    "me gasté", "sali", "salió", "costo", "costó", "di", "invertí en",
}

# números en palabras, para "veinte mil" además de "20000" o "20 mil"
UNIDADES = {
    "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiun": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27,
    "veintiocho": 28, "veintinueve": 29,
}
DECENAS = {
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90,
}


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _numero_en_palabras_a_int(texto: str) -> int | None:
    """'veinte' -> 20, 'treinta y cinco' -> 35, 'cien' -> 100."""
    texto = texto.strip()
    if texto in UNIDADES:
        return UNIDADES[texto]
    if texto in DECENAS:
        return DECENAS[texto]
    if texto in ("cien", "cien "):
        return 100
    match = re.match(r"^(\w+)\s+y\s+(\w+)$", texto)
    if match and match.group(1) in DECENAS and match.group(2) in UNIDADES:
        return DECENAS[match.group(1)] + UNIDADES[match.group(2)]
    return None


def _numero_directo_a_float(texto_numero: str) -> float:
    """'15.000' (separador de miles CO) -> 15000.0, pero '1.5' (decimal) -> 1.5.
    Un punto/coma seguido de EXACTAMENTE 3 dígitos y nada más después es
    separador de miles; cualquier otro caso se trata como decimal."""
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", texto_numero):
        return float(re.sub(r"[.,]", "", texto_numero))
    return float(texto_numero.replace(",", "."))


def extraer_monto(texto_original: str) -> float | None:
    texto = _sin_tildes(texto_original.lower())

    # formato numérico directo: "20000", "20.000", "20 mil", "1.5 millones"
    match = re.search(
        r"(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(millon(?:es)?|mil|k)?\b",
        texto,
    )
    if match and re.search(r"\d", match.group(0)):
        base = _numero_directo_a_float(match.group(1))
        sufijo = match.group(2)
        if sufijo in ("mil", "k"):
            base *= 1000
        elif sufijo and "millon" in sufijo:
            base *= 1_000_000
        if base > 0:
            return base

    # formato en palabras: "veinte mil", "cien mil", "treinta y cinco mil"
    match = re.search(
        r"([a-z]+(?:\s+y\s+[a-z]+)?)\s+mil\b",
        texto,
    )
    if match:
        numero = _numero_en_palabras_a_int(match.group(1))
        if numero:
            return float(numero * 1000)
    if re.search(r"\bcien\s+mil\b", texto):
        return 100_000.0

    return None


def detectar_tipo(texto_original: str) -> str:
    texto = _sin_tildes(texto_original.lower())
    for palabra in PALABRAS_INGRESO:
        if _sin_tildes(palabra) in texto:
            return "income"
    return "expense"


def extraer_descripcion(texto_original: str, monto_texto_detectado: str = "") -> str:
    """Se queda con lo que sobra de la frase después de quitar el monto y
    las palabras de acción, para usarlo como descripción legible."""
    texto = texto_original.strip()
    texto = re.sub(r"\d+(?:[.,]\d+)?\s*(millones?|mil|k)?\b", "", texto, flags=re.IGNORECASE)
    for palabra in sorted(PALABRAS_INGRESO | PALABRAS_GASTO, key=len, reverse=True):
        texto = re.sub(re.escape(palabra), "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"^\s*(en|de|del|la|el|los|las)\s+", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s{2,}", " ", texto).strip(" .,")
    return texto.capitalize() if texto else "Movimiento por voz"


def interpretar_frase(texto: str) -> dict | None:
    """Devuelve {monto, tipo, descripcion} o None si no se pudo entender
    lo mínimo (el monto) — en ese caso el usuario debe confirmar a mano."""
    if not texto or not texto.strip():
        return None

    monto = extraer_monto(texto)
    if not monto:
        return None

    return {
        "monto": monto,
        "tipo": detectar_tipo(texto),
        "descripcion": extraer_descripcion(texto),
    }
