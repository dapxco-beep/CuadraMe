"""
Última capa de clasificación: palabras clave de comercios y conceptos
bancarios de Colombia. Se usa solo si el usuario no tiene una regla propia ni
historial suficiente para que el modelo aprendido decida.

Los DATOS viven en diccionario_categorias.py; aquí solo está el motor que los
busca. Coincide por palabras completas (así 'ara' no se activa dentro de
'para') y gana la entrada más específica.
"""
import re
import unicodedata

from app.costos_financieros import clasificar_costo
from app.diccionario_categorias import (
    BRE_B_FRASES,
    BRE_B_PALABRAS_ENTRADA,
    PASARELAS,
    INVERSION_PRIORITARIA,
    TRANSFERENCIA_ENTRADA,
    TRANSFERENCIA_PERSONA_INICIO,
    TRANSFERENCIA_PERSONA_DEBIL,
    TRANSFERENCIA_PERSONA_FUERTE,
    entradas,
)


def normalizar(texto: str) -> str:
    """minúsculas, sin tildes, solo letras/números separados por un espacio."""
    t = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _indexar():
    indice = []
    for palabra, categoria, tipo in entradas():
        prefijo = palabra.endswith("*")
        pat = normalizar(palabra.rstrip("*"))
        if not pat:
            continue
        indice.append((len(pat.split()), len(pat), pat, prefijo, categoria, tipo, palabra.rstrip("*")))
    # más palabras primero, luego más largo: 'uber eats' antes que 'uber'
    # a igualdad, un ingreso explícito ('nomina') gana: 'NOMINA SKANDIA' es ingreso, no inversión
    indice.sort(key=lambda e: (-e[0], e[5] != "income", -e[1]))
    return indice


_INDICE = _indexar()


def _coincide(texto_pad: str, pat: str, prefijo: bool) -> bool:
    return (f" {pat}" in texto_pad) if prefijo else (f" {pat} " in texto_pad)


def _transferencia(texto_pad: str, frases: list[str]) -> dict | None:
    for frase in frases:
        if _coincide(texto_pad, normalizar(frase), False):
            tipo = "income" if frase in TRANSFERENCIA_ENTRADA else "expense"
            # Confianza baja a propósito: una transferencia a otra persona puede ser un gasto
            # real o plata que se presta, así que nunca se auto-importa sola.
            return {
                "categoria": "Transferencias", "tipo": tipo, "confianza": 0.5, "fuente": "diccionario",
                "palabra": frase, "razon": f"por palabra clave «{frase}»",
            }
    return None


def _inversion_prioritaria(texto_pad: str) -> dict | None:
    for frase in INVERSION_PRIORITARIA:
        pat = normalizar(frase.rstrip("*"))
        if _coincide(texto_pad, pat, frase.endswith("*")):
            return {
                "categoria": "Ahorro e inversión", "tipo": "expense", "confianza": 0.75, "fuente": "diccionario",
                "palabra": frase.rstrip("*"), "razon": f"por palabra clave «{frase.rstrip('*')}»",
            }
    return None


def _transferencia_al_inicio(texto_pad: str) -> dict | None:
    """'Para <persona>' / 'De <persona>' al comienzo de la línea (extractos tipo Nequi)."""
    for palabra, tipo in TRANSFERENCIA_PERSONA_INICIO.items():
        if texto_pad.startswith(f" {palabra} ") and len(texto_pad.split()) >= 2:
            return {
                "categoria": "Transferencias", "tipo": tipo, "confianza": 0.5, "fuente": "diccionario",
                "palabra": palabra, "razon": f"por palabra clave «{palabra}»",
            }
    return None


_RE_PASARELA = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(p).replace(r"\ ", r"\s*") for p in sorted(PASARELAS, key=len, reverse=True))
    + r")\s*\*\s*([^*]+)$",
    re.IGNORECASE,
)


def _comercio_tras_pasarela(descripcion: str) -> dict | None:
    """'BOLD*Cafe Luna' / 'PAYU*SPOTIFY': el comercio real va tras el asterisco, así que
    se clasifica solo ese nombre (el de la pasarela no dice nada del gasto)."""
    m = _RE_PASARELA.search(descripcion or "")
    if not m:
        return None
    comercio = m.group(2).strip()
    texto_pad = f" {normalizar(comercio)} "
    if texto_pad.strip() == "":
        return None
    for _n, _l, pat, prefijo, categoria, tipo, original in _INDICE:
        if _coincide(texto_pad, pat, prefijo):
            pasarela = m.group(1).upper()
            return {
                "categoria": categoria, "tipo": tipo, "confianza": 0.75, "fuente": "diccionario",
                "palabra": original, "razon": f"por el comercio «{comercio}» (pagado con {pasarela})",
            }
    return None


def _bre_b(texto_pad: str) -> dict | None:
    """Bre-B / transferencia inmediata -> Transferencias; el tipo depende de si se recibió."""
    for frase in BRE_B_FRASES:
        if _coincide(texto_pad, normalizar(frase), False):
            entra = any(f" {p} " in texto_pad for p in BRE_B_PALABRAS_ENTRADA)
            return {
                "categoria": "Transferencias", "tipo": "income" if entra else "expense", "confianza": 0.5,
                "fuente": "diccionario", "palabra": frase, "razon": f"por palabra clave «{frase}»",
            }
    return None


def clasificar_por_diccionario(descripcion: str) -> dict | None:
    # Cobros y rendimientos bancarios (intereses, cuota de manejo, comisiones, 4x1000): por patrón de línea.
    costo = clasificar_costo(descripcion)
    if costo:
        return costo

    texto_pad = f" {normalizar(descripcion)} "

    r = _comercio_tras_pasarela(descripcion) or _bre_b(texto_pad)
    if r:
        return r

    r = _inversion_prioritaria(texto_pad) or _transferencia(texto_pad, TRANSFERENCIA_PERSONA_FUERTE) \
        or _transferencia_al_inicio(texto_pad)
    if r:
        return r

    for _n, _l, pat, prefijo, categoria, tipo, original in _INDICE:
        if _coincide(texto_pad, pat, prefijo):
            return {
                "categoria": categoria, "tipo": tipo, "confianza": 0.75, "fuente": "diccionario",
                "palabra": original, "razon": f"por palabra clave «{original}»",
            }

    return _transferencia(texto_pad, TRANSFERENCIA_PERSONA_DEBIL)
