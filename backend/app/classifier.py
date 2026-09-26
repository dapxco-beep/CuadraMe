"""
Clasificador de movimientos por frecuencia de tokens (Naive Bayes simplificado).
Migrado de LearnedClassifier.js: aprende de las categorías que el usuario
ya ha asignado a sus propios movimientos, sin necesitar entrenamiento previo.
"""
import math
import re
import unicodedata
from collections import defaultdict

MIN_TOKEN_LEN = 3
MIN_CONFIANZA = 0.55

STOPWORDS = {
    "de", "la", "el", "en", "a", "por", "con", "para", "del", "los",
    "las", "un", "una", "y", "o", "pago", "compra", "abono", "cargo",
    "transferencia", "transf", "movimiento", "ref", "no", "nro", "col",
    "cop", "pse", "debito", "credito", "tarjeta", "cuenta",
}


def tokenize(texto: str) -> list[str]:
    texto = texto.lower()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    tokens = texto.split()
    return [
        t for t in tokens
        if len(t) >= MIN_TOKEN_LEN and t not in STOPWORDS and not t.isdigit()
    ]


def build_model(movimientos: list[dict]) -> dict:
    """movimientos: [{descripcion, categoria, tipo}], ya categorizados por el usuario."""
    tokens_por_cat = defaultdict(lambda: defaultdict(int))
    cat_count = defaultdict(int)
    cat_tipo = defaultdict(lambda: defaultdict(int))
    total = 0

    for m in movimientos:
        cat = (m.get("categoria") or "").strip()
        if not cat or cat.lower() == "otros":
            continue
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

    for tok in tokens:
        dist = model["tokens"].get(tok)
        if not dist:
            continue
        matched += 1
        total_tok = sum(dist.values())
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
    confianza = min(0.97, 0.4 + dominancia * 0.45 + cobertura * 0.15)

    if confianza < MIN_CONFIANZA:
        return None

    tipos = model["cat_tipo"].get(best_cat, {})
    tipo = max(tipos, key=tipos.get) if tipos else "expense"

    return {
        "categoria": best_cat,
        "tipo": tipo,
        "confianza": round(confianza, 2),
        "fuente": "learned",
    }
