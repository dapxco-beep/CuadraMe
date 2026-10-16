"""Memoria y señales POR USUARIO para categorizar (Python puro, sin dependencias).

Dos piezas, ambas armadas al vuelo con los movimientos que ESE usuario confirmó
(nunca se comparten entre usuarios):

1) MEMORIA del beneficiario/comercio: cuántas veces confirmó cada categoría para la
   misma «clave» (el nombre ya limpio, sea comercio o persona). Como es del propio
   usuario, aquí SÍ se aprende de nombres propios: «siempre le pago a esta persona el
   arriendo». Lo que no se hace es llevar ese nombre a otro usuario ni aprender de un
   caso ambiguo.
   - 1 confirmación            -> sugerencia con confianza media («aprendida de tu historial»)
   - >= 2 concordantes         -> confianza alta
   - dos categorías en pugna   -> «ambiguo»: no se propone y se ofrecen sus 2 opciones habituales

2) SEÑALES (naive Bayes pequeño e interpretable): tipo ingreso/gasto, rango de monto,
   si el monto es redondo, día del mes, tipo de cuenta, palabras de la pasarela (PSE, DLO,
   BOLD...), si es persona y si la misma clave se repite en >= 3 meses. Siempre puede
   abstenerse: devuelve None cuando la probabilidad queda bajo el umbral.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from app.clave_comercio import _limpiar, _sin_tildes, es_transferencia_entre_personas

# Confianzas de la memoria (calibradas con la evaluación «dejar uno fuera», ver docs/MODELO_CATEGORIAS.md).
CONF_UNA_VEZ = 0.75
CONF_CONCORDANTE_BASE = 0.80
CONF_CONCORDANTE_MAX = 0.95
# La categoría líder debe tener al menos el doble de confirmaciones que la segunda; si no, es ambiguo.
RAZON_DOMINANCIA = 2.0

# Umbral de operación: por debajo, la categoría es «tentativa» y no se presenta como propuesta firme.
UMBRAL_PROPUESTA = 0.80
# Umbral para que el modelo de señales proponga algo por sí solo.
UMBRAL_SENALES = 0.85
# Temperatura del naive Bayes (las señales están correlacionadas: se enfría para no sobreconfiar).
TEMPERATURA = 2.0
MIN_HISTORIAL_SENALES = 20

PASARELAS = ("pse", "dlo", "dlocal", "bold", "nequi", "daviplata", "bre", "qr", "payu", "mercpago",
             "wompi", "epayco", "sumup", "pagaste", "enviaste", "recibiste", "transferencia", "nomina",
             "cuota", "abono", "retiro", "compra")


def clave_beneficiario(descripcion: str | None) -> str:
    """Nombre limpio de a quién/dónde se pagó. Para personas conserva hasta 4 palabras (el apellido
    importa); para comercios es la misma huella de 3 palabras."""
    palabras = _limpiar(descripcion)
    tope = 4 if es_transferencia_entre_personas(descripcion) else 3
    return " ".join(palabras[:tope])


def _mes(fecha) -> str:
    return str(fecha or "")[:7]


def construir_memoria(movs: list[dict]) -> dict:
    """movs: [{descripcion, categoria, tipo?, fecha?}] confirmados por el usuario."""
    cats: dict[str, Counter] = defaultdict(Counter)
    meses: dict[str, set] = defaultdict(set)
    tipos: dict[str, Counter] = defaultdict(Counter)
    subs: dict[tuple, Counter] = defaultdict(Counter)  # (clave, categoria) -> subcategorías que el usuario ya usó
    for m in movs:
        cat = (m.get("categoria") or "").strip()
        if not cat or cat.lower() == "otros":
            continue
        k = clave_beneficiario(m.get("descripcion"))
        if not k:
            continue
        cats[k][cat] += 1
        if (m.get("subcategoria") or "").strip():
            subs[(k, cat)][m["subcategoria"].strip()] += 1
        if m.get("tipo"):
            tipos[k][m["tipo"]] += 1
        if _mes(m.get("fecha")):
            meses[k].add(_mes(m.get("fecha")))
    return {"cats": cats, "meses": meses, "tipos": tipos, "subs": subs}


def subcategoria_habitual(memoria: dict | None, clave: str, categoria: str) -> str | None:
    """Subcategoría que el usuario YA usó con este comercio dentro de esa categoría, solo si domina
    (más de la mitad de las veces que lo categorizó así). Nunca se inventa una."""
    c = ((memoria or {}).get("subs") or {}).get((clave, categoria))
    if not c:
        return None
    total_cat = (memoria["cats"].get(clave) or {}).get(categoria, 0)
    nombre, n = c.most_common(1)[0]
    return nombre if total_cat and n * 2 > total_cat else None


def consultar_memoria(descripcion: str, memoria: dict | None) -> dict | None:
    """None si no hay historial de esa clave. Si lo hay:
    {estado: 'una_vez'|'concordante'|'ambiguo', categoria, n, confianza, tipo, opciones:[(cat, n), ...]}"""
    if not memoria:
        return None
    k = clave_beneficiario(descripcion)
    c = memoria["cats"].get(k)
    if not c:
        return None
    ordenadas = c.most_common()
    (cat1, n1) = ordenadas[0]
    n2 = ordenadas[1][1] if len(ordenadas) > 1 else 0
    total = sum(c.values())
    opciones = ordenadas[:2]
    tp = memoria.get("tipos", {}).get(k)
    tipo = tp.most_common(1)[0][0] if tp else None
    sub_hab = subcategoria_habitual(memoria, k, cat1)
    if n2 and n1 < RAZON_DOMINANCIA * n2:
        return {"estado": "ambiguo", "categoria": None, "n": total, "confianza": 0.0, "tipo": tipo, "opciones": opciones}
    if n1 == 1 and total == 1:
        return {"estado": "una_vez", "categoria": cat1, "n": 1, "confianza": CONF_UNA_VEZ, "tipo": tipo, "opciones": opciones,
                "subcategoria": sub_hab}
    pureza = n1 / total
    conf = min(CONF_CONCORDANTE_MAX, CONF_CONCORDANTE_BASE + 0.05 * (n1 - 2)) * (0.6 + 0.4 * pureza) \
        if n1 >= 2 else CONF_UNA_VEZ * pureza
    estado = "concordante" if n1 >= 2 else "una_vez"
    return {"estado": estado, "categoria": cat1, "n": total, "confianza": round(conf, 2), "tipo": tipo, "opciones": opciones,
            "subcategoria": sub_hab}


# --- señales -------------------------------------------------------------------

def _bucket_monto(monto: float) -> str:
    m = abs(monto or 0)
    if m <= 0:
        return "m0"
    return f"m{int(math.floor(math.log10(m) * 2))}"  # medias décadas: 10k-31k, 31k-100k...


def _redondez(monto: float) -> str:
    m = int(round(abs(monto or 0)))
    if m and m % 100000 == 0:
        return "r100k"
    if m and m % 10000 == 0:
        return "r10k"
    if m and m % 1000 == 0:
        return "r1k"
    return "r0"


def _dia(fecha) -> str | None:
    s = str(fecha or "")
    mt = re.match(r"\d{4}-\d{2}-(\d{2})", s)
    if not mt:
        return None
    d = int(mt.group(1))
    return f"d{(d - 1) // 5}"  # 1-5, 6-10, ... 26-31


def rasgos(descripcion: str, contexto: dict | None, recurrente: bool = False) -> list[str]:
    """Lista de rasgos (strings) del movimiento; solo los que se conocen."""
    ctx = contexto or {}
    f = []
    if ctx.get("tipo"):
        f.append(f"tipo:{ctx['tipo']}")
    if ctx.get("monto") is not None:
        f.append("monto:" + _bucket_monto(ctx["monto"]))
        f.append("red:" + _redondez(ctx["monto"]))
        f.append(f"exacto:{int(round(abs(ctx['monto'])))}")  # el mismo valor exacto (cuota, suscripción, arriendo)
    d = _dia(ctx.get("fecha"))
    if d:
        f.append("dia:" + d)
    if ctx.get("cuenta_tipo"):
        f.append(f"cuenta:{ctx['cuenta_tipo']}")
    texto = _sin_tildes((descripcion or "").lower())
    toks = set(re.findall(r"[a-z]+", texto))
    for p in PASARELAS:
        if p in toks:
            f.append(f"pas:{p}")
    if es_transferencia_entre_personas(descripcion):
        f.append("persona")
    if recurrente:
        f.append("recurrente")
    return f


def _es_recurrente(descripcion: str, memoria: dict | None, min_meses: int = 3) -> bool:
    if not memoria:
        return False
    return len(memoria["meses"].get(clave_beneficiario(descripcion), ())) >= min_meses


def construir_senales(movs: list[dict], memoria: dict | None = None) -> dict:
    memoria = memoria if memoria is not None else construir_memoria(movs)
    por_cat: dict[str, Counter] = defaultdict(Counter)
    n_cat: Counter = Counter()
    vocab: set[str] = set()
    for m in movs:
        cat = (m.get("categoria") or "").strip()
        if not cat or cat.lower() == "otros":
            continue
        fs = rasgos(m.get("descripcion"), m, _es_recurrente(m.get("descripcion"), memoria))
        n_cat[cat] += 1
        for x in fs:
            por_cat[cat][x] += 1
            vocab.add(x)
    return {"por_cat": por_cat, "n_cat": n_cat, "vocab": vocab, "total": sum(n_cat.values())}


def predecir_senales(descripcion: str, contexto: dict | None, modelo: dict | None,
                     memoria: dict | None = None, umbral: float | None = None) -> dict | None:
    """{categoria, confianza, razon} o None (abstención). La probabilidad es el posterior de un
    naive Bayes con suavizado de Laplace y temperatura."""
    if not modelo or modelo["total"] < MIN_HISTORIAL_SENALES:
        return None
    fs = rasgos(descripcion, contexto, _es_recurrente(descripcion, memoria))
    if not fs:
        return None
    total = modelo["total"]
    logs: dict[str, float] = {}
    for cat, n in modelo["n_cat"].items():
        s = math.log(n / total)
        for x in fs:
            s += math.log((modelo["por_cat"][cat].get(x, 0) + 0.5) / (n + 1.0)) / TEMPERATURA
        logs[cat] = s
    mx = max(logs.values())
    exp = {c: math.exp(v - mx) for c, v in logs.items()}
    z = sum(exp.values())
    best = max(exp, key=exp.get)
    p = exp[best] / z
    if p < (UMBRAL_SENALES if umbral is None else umbral):
        return None
    return {"categoria": best, "confianza": round(min(0.9, p), 2), "razon": "por monto, día y tipo de movimientos parecidos"}
