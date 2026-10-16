"""
Clasificador de movimientos por frecuencia de tokens (Naive Bayes simplificado).
Migrado de LearnedClassifier.js: aprende de las categorías que el usuario
ya ha asignado a sus propios movimientos, sin necesitar entrenamiento previo.
"""
import math
import re
import unicodedata
from collections import defaultdict

from app.costos_financieros import NOMBRES_SISTEMA
from app.clave_comercio import (
    clave_comercio, es_transferencia_entre_personas, huella_en_descripcion, palabras_comercio,
)

MIN_TOKEN_LEN = 3
MIN_CONFIANZA = 0.55
EVIDENCIA_MEDIA = 1.0  # con este número de observaciones la evidencia vale la mitad

STOPWORDS = {
    "de", "la", "el", "en", "a", "por", "con", "para", "del", "los",
    "las", "un", "una", "y", "o", "pago", "compra", "abono", "cargo",
    "transferencia", "transf", "movimiento", "ref", "no", "nro", "col",
    "cop", "pse", "debito", "credito", "tarjeta", "cuenta",
}


# Palabras que describen el LUGAR o la operación, no el comercio: no sirven de señal.
GENERICAS = {
    "centro", "comercial", "zona", "tienda", "plaza", "local", "punto", "almacen", "cajero",
    "pagaste", "enviaste", "recibiste", "envio", "recibi", "bre", "llave", "inmediata", "nuestro",
}


def tokenize(texto: str) -> list[str]:
    """Palabras que identifican al COMERCIO: sin prefijos de pasarela ('PAGO PSE', 'BOLD*',
    'Pagaste en'), ciudades, NIT ni códigos (las quita clave_comercio.palabras_comercio).
    De una transferencia entre personas ('Para <nombre>') no se aprende nada: un nombre
    propio no dice en qué se gastó la plata."""
    if es_transferencia_entre_personas(texto):
        return []
    return [
        t for t in palabras_comercio(texto)
        if len(t) >= MIN_TOKEN_LEN and t not in STOPWORDS and t not in GENERICAS and not t.isdigit()
    ]


def build_model(movimientos: list[dict]) -> dict:
    """movimientos: [{descripcion, categoria, tipo}], ya categorizados por el usuario."""
    tokens_por_cat = defaultdict(lambda: defaultdict(int))
    cat_count = defaultdict(int)
    cat_tipo = defaultdict(lambda: defaultdict(int))
    total = 0

    for m in movimientos:
        cat = (m.get("categoria") or "").strip()
        if not cat or cat.lower() == "otros" or cat in NOMBRES_SISTEMA:
            continue  # las categorías de sistema (4x1000, intereses...) las decide el banco, no el historial
        desc = (m.get("descripcion") or "").strip()
        tipo = m.get("tipo") or ""
        if not desc:
            continue

        cat_count[cat] += 1
        total += 1
        if tipo:
            cat_tipo[cat][tipo] += 1

        seen = set()
        for tok in tokenize(desc):
            if tok in seen:
                continue
            seen.add(tok)
            tokens_por_cat[tok][cat] += 1

    return {"tokens": tokens_por_cat, "cats": cat_count, "cat_tipo": cat_tipo, "total": total}


def classify(descripcion: str, model: dict) -> dict | None:
    if not model["total"]:
        return None

    tokens = tokenize(descripcion)
    if not tokens:
        return None

    votes = defaultdict(float)
    matched = 0
    observaciones = 0  # cuántas veces vio el usuario las palabras que coinciden (la evidencia)

    for tok in tokens:
        dist = model["tokens"].get(tok)
        if not dist:
            continue
        matched += 1
        total_tok = sum(dist.values())
        observaciones += total_tok
        for cat, count in dist.items():
            peso = (count / total_tok) * (1 + math.log(1 + count))
            votes[cat] += peso

    if not matched:
        return None

    best_cat = max(votes, key=votes.get)
    best_score = votes[best_cat]
    sum_score = sum(votes.values())

    dominancia = best_score / sum_score if sum_score > 0 else 0
    cobertura = min(1, matched / max(1, len(tokens)))
    # Poca evidencia = poca confianza: una palabra vista UNA vez no es lo mismo que vista diez.
    evidencia = observaciones / (observaciones + EVIDENCIA_MEDIA)
    confianza = min(0.97, 0.4 + dominancia * 0.45 * evidencia + cobertura * 0.15)

    if confianza < MIN_CONFIANZA:
        return None

    tipos = model["cat_tipo"].get(best_cat, {})
    tipo = max(tipos, key=tipos.get) if tipos else "expense"

    return {
        "categoria": best_cat,
        "tipo": tipo,
        "confianza": round(confianza, 2),
        "fuente": "learned",
        "razon": "similar a movimientos tuyos",
    }


def _resultado_regla(regla, huella: str) -> dict:
    return {
        "categoria": regla.categoria,
        "subcategoria": getattr(regla, "subcategoria", None),
        "tipo": regla.tipo,
        "confianza": 1.0,
        "fuente": "regla",
        "palabra": huella,
        "razon": f"por tu regla «{huella}»",
    }


def aplicar_reglas(descripcion: str, reglas: list) -> dict | None:
    """reglas: objetos ReglaCategoria, ya ordenados por prioridad desc.
    1) coincidencia EXACTA de huella de comercio (clave_comercio) y, si no hay,
    2) por 'contiene': el patrón dentro de la descripción, o su huella como
    palabras completas dentro de la huella de la descripción."""
    # Una regla en pausa (activa = False) no se aplica; NULL (reglas viejas) cuenta como activa.
    reglas = [r for r in reglas if getattr(r, "activa", True) is not False]
    huella = clave_comercio(descripcion)
    if huella:
        for regla in reglas:
            if clave_comercio(regla.patron) == huella:
                return _resultado_regla(regla, huella)
    desc_lower = descripcion.lower()
    for regla in reglas:
        patron = regla.patron.strip()
        if not patron:
            continue
        # Patrones cortos ('d1', 'kfc') solo cuentan como palabra completa (vía huella): 'd1' no debe
        # activarse dentro de 'cod12345'.
        if len(patron) >= 4 and patron.lower() in desc_lower:
            return _resultado_regla(regla, clave_comercio(patron) or patron.lower())
        hp = clave_comercio(patron)
        if hp and huella_en_descripcion(hp, descripcion):
            return _resultado_regla(regla, hp)
    return None
