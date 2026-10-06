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

from app.diccionario_categorias import (
    TRANSFERENCIA_ENTRADA,
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


def clasificar_por_diccionario(descripcion: str) -> dict | None:
    texto_pad = f" {normalizar(descripcion)} "

    r = _transferencia(texto_pad, TRANSFERENCIA_PERSONA_FUERTE)
    if r:
        return r

    for _n, _l, pat, prefijo, categoria, tipo, original in _INDICE:
        if _coincide(texto_pad, pat, prefijo):
            return {
                "categoria": categoria, "tipo": tipo, "confianza": 0.75, "fuente": "diccionario",
                "palabra": original, "razon": f"por palabra clave «{original}»",
            }

    return _transferencia(texto_pad, TRANSFERENCIA_PERSONA_DEBIL)
