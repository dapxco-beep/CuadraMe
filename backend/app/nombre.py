"""Cómo le decimos a cada persona: nombre de pila amable y validación del nombre que escribe.

Minimización (Ley 1581): solo se guarda UN nombre corto, el que la persona quiere que usemos.
Google entrega el nombre completo («DANIEL ALFONSO PARRADO CARDENAS»); de ahí sale un nombre de
pila sugerido, que la persona puede corregir. Se usa en la app, el resumen semanal y el push.
Nunca en lugares públicos ni en el panel de administración."""
import re
import unicodedata

MAX_NOMBRE = 40
_SEPARADORES = "-'’"


class NombreInvalido(ValueError):
    """El mensaje ya está listo para mostrarse a la persona."""


def _normalizar(texto) -> str:
    texto = unicodedata.normalize("NFC", str(texto or ""))
    return re.sub(r"\s+", " ", texto).strip()


def _capitalizar_token(token: str) -> str:
    # «o'brien» -> «O'Brien», «ana-maría» -> «Ana-María». Las tildes se conservan.
    partes = re.split(f"([{re.escape(_SEPARADORES)}])", token)
    return "".join(p.capitalize() if p and p not in _SEPARADORES else p for p in partes)


def _embellecer(texto: str) -> str:
    """Si viene todo en mayúsculas o todo en minúsculas lo deja en formato «Nombre».
    Si ya trae mayúsculas mixtas (McDonald, De la Cruz) se respeta tal cual."""
    if texto.isupper() or texto.islower():
        return " ".join(_capitalizar_token(t) for t in texto.split(" "))
    return texto


def _es_letra_o_marca(c: str) -> bool:
    return c.isalpha() or unicodedata.category(c).startswith("M")


def _solo_nombre(token: str) -> str:
    return "".join(c for c in token if _es_letra_o_marca(c) or c in _SEPARADORES).strip(_SEPARADORES)


def nombre_de_pila(nombre_completo=None, nombre_pila_google=None) -> str:
    """Nombre de pila sugerido, o '' si no hay de dónde sacarlo.
    - Con `given_name` de Google: se respeta si es compuesto (hasta 2 palabras, «María José»).
    - Solo con el nombre completo: primera palabra («DANIEL ALFONSO PARRADO» -> «Daniel»).
    - Un correo no es un nombre: si parece correo o trae números, no se usa."""
    for fuente, max_tokens in ((nombre_pila_google, 2), (nombre_completo, 1)):
        texto = _normalizar(fuente)
        if not texto or "@" in texto:
            continue
        tokens = [t for t in (_solo_nombre(t) for t in texto.split(" ")) if t]
        if not tokens:
            continue
        candidato = _embellecer(" ".join(tokens[:max_tokens]))
        try:
            return validar_nombre(candidato)
        except NombreInvalido:
            continue
    return ""


def validar_nombre(texto) -> str:
    """Nombre limpio (recortado, sin espacios dobles) o NombreInvalido con mensaje amable.
    Permite letras, tildes, espacios, guion y apóstrofo. Rechaza el resto (HTML, enlaces,
    números, emojis)."""
    limpio = _normalizar(texto)
    if not limpio:
        raise NombreInvalido("Escribe cómo quieres que te llamemos.")
    if len(limpio) > MAX_NOMBRE:
        raise NombreInvalido(f"Que sea más corto, por favor (máximo {MAX_NOMBRE} letras).")
    if not all(_es_letra_o_marca(c) or c in _SEPARADORES or c == " " for c in limpio):
        raise NombreInvalido("Usa solo letras, espacios, guion o apóstrofo (sin números, emojis ni símbolos).")
    if not any(c.isalpha() for c in limpio):
        raise NombreInvalido("Escribe al menos una letra.")
    return _embellecer(limpio)


def nombre_para_mostrar(preferido) -> str:
    """Lo que se usa en saludos, correos y avisos: el nombre guardado o '' (jamás un dato inventado)."""
    return (preferido or "").strip()
