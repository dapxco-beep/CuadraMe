"""Evaluación OFFLINE y reproducible del clasificador de categorías.

Uso (desde backend/):
    python tools/evaluar_clasificador.py RUTA_AL_EXPORT.json [--top 10] [--min-confianza 0.55]
                                         [--salida-json agregados.json] [--mostrar-errores]

El JSON es una lista de movimientos con el formato del export de la app (campos:
descripcion, categoria, tipo, cat_confirmada...). Solo se usan los CONFIRMADOS por la
persona: lo que la app puso sola no sirve de verdad de referencia.

Para no hacer trampa se usa «dejar fuera un comercio»: cada movimiento se clasifica con un
modelo armado SIN ningún movimiento de su misma huella de comercio (así la categoría no se
«copia» de un duplicado exacto). Usa la misma función de decisión que producción
(autocat.decidir_categoria), con el diccionario y el modelo aprendido.

PRIVACIDAD: por defecto solo imprime agregados. Los comercios que más fallan salen
enmascarados, salvo marcas públicas reconocidas por el diccionario. --mostrar-errores
imprime descripciones crudas: úsese SOLO en la máquina del dueño de los datos.
Los datos no se copian ni se guardan en ninguna parte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Nunca tocar la base real: el script no necesita base de datos.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import classifier  # noqa: E402
from app.autocat import _BASE, decidir_categoria  # noqa: E402
from app.clave_comercio import clave_comercio, es_transferencia_entre_personas  # noqa: E402
from app.comercios_conocidos import clasificar_por_diccionario  # noqa: E402

# Categorías del diccionario cuya «palabra» NO es una marca (frases de transferencia entre personas, etc.)
_NO_MARCA = {"Transferencias", "Ingresos"}
OTROS = "Otros"


def _reparar(texto: str) -> str:
    """Algunos exports traen UTF-8 leído como Latin-1 ('dÃ©bito'): se deshace si aplica."""
    if "Ã" in texto or "Â" in texto:
        try:
            return texto.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return texto
    return texto


def cargar_confirmados(ruta: str) -> list[dict]:
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    if isinstance(datos, dict):
        datos = datos.get("movimientos") or datos.get("items") or []
    salida = []
    for m in datos:
        if m.get("cat_confirmada") is False:
            continue
        desc = _reparar(m.get("descripcion") or "").strip()
        cat = _reparar(m.get("categoria") or "").strip()
        if desc and cat:
            salida.append({"descripcion": desc, "categoria": cat, "tipo": m.get("tipo") or ""})
    return salida


def _grupo(desc: str) -> str:
    return clave_comercio(desc) or desc.lower()


def enmascarar(huella: str, desc_ejemplo: str) -> str:
    """Marca pública (por diccionario) -> su palabra clave; si no, 'x***-<hash>'."""
    r = clasificar_por_diccionario(desc_ejemplo)
    if r and r.get("categoria") not in _NO_MARCA and r.get("fuente") == "diccionario" and r.get("palabra"):
        return f"[marca] {r['palabra']}"
    h = hashlib.sha256(huella.encode()).hexdigest()[:6]
    return f"{huella[:1]}***-{h}"


def evaluar(movs: list[dict], min_confianza: float | None = None, modo: str = "comercio") -> dict:
    """modo='comercio': deja fuera todos los movimientos del mismo comercio (¿qué tal con comercios NUEVOS?).
    modo='movimiento': deja fuera solo el movimiento evaluado (¿qué tal con los comercios que ya repetiste?)."""
    if min_confianza is not None:
        classifier.MIN_CONFIANZA = min_confianza
    activas = {m["categoria"].lower() for m in movs} | set(_BASE)
    grupos: dict[str, list[int]] = defaultdict(list)
    for i, m in enumerate(movs):
        grupos[_grupo(m["descripcion"])].append(i)

    resultados: list[dict | None] = [None] * len(movs)
    if modo == "movimiento":
        for i, m in enumerate(movs):
            modelo = classifier.build_model(movs[:i] + movs[i + 1:])
            resultados[i] = decidir_categoria(m["descripcion"], [], modelo, activas)
    else:
        for huella, idx in grupos.items():
            resto = [m for m in movs if _grupo(m["descripcion"]) != huella]
            modelo = classifier.build_model(resto)
            for i in idx:
                resultados[i] = decidir_categoria(movs[i]["descripcion"], [], modelo, activas)

    n = len(movs)
    filas = []
    for m, r in zip(movs, resultados):
        filas.append({
            "real": m["categoria"], "pred": r["categoria"] if r else OTROS,
            "fuente": (r or {}).get("fuente", "ninguna"), "conf": (r or {}).get("confianza"),
            "grupo": _grupo(m["descripcion"]), "desc": m["descripcion"],
            "persona": es_transferencia_entre_personas(m["descripcion"]),
        })

    def ok(f):
        return f["real"].lower() == f["pred"].lower()

    propuestas = [f for f in filas if f["pred"] != OTROS]
    reales_no_otros = [f for f in filas if f["real"] != OTROS]
    # Segmentos: una transferencia entre personas ('Para <nombre>') NO dice en qué se gastó la plata;
    # lo correcto es proponer «Transferencias» (con confianza baja) y preguntar. Se mide aparte para
    # que la exactitud de los COMERCIOS (donde el modelo sí puede saber) no se diluya.
    personas = [f for f in filas if f["persona"]]
    comercios = [f for f in filas if not f["persona"]]
    comercios_reales = [f for f in comercios if f["real"] != OTROS]
    segmentos = {
        "n_personas": len(personas),
        "personas_propuestas_como_transferencias": round(
            sum(f["pred"] == "Transferencias" for f in personas) / len(personas), 3) if personas else 0,
        "personas_que_la_persona_dejo_como_transferencias": round(
            sum(f["real"] == "Transferencias" for f in personas) / len(personas), 3) if personas else 0,
        "n_comercios": len(comercios),
        "exactitud_comercios": round(sum(map(ok, comercios)) / len(comercios), 3) if comercios else 0,
        "exactitud_comercios_sin_otros_reales": round(
            sum(map(ok, comercios_reales)) / len(comercios_reales), 3) if comercios_reales else 0,
        "exactitud_comercios_propuestos": round(
            sum(map(ok, [f for f in comercios if f["pred"] != OTROS])) /
            max(1, len([f for f in comercios if f["pred"] != OTROS])), 3),
        "cobertura_otros_comercios": round(
            sum(f["pred"] == OTROS for f in comercios) / len(comercios), 3) if comercios else 0,
    }
    por_cat = {}
    for cat in sorted({f["real"] for f in filas}):
        fs = [f for f in filas if f["real"] == cat]
        por_cat[cat] = {
            "n": len(fs),
            "exactitud": round(sum(f["pred"].lower() == cat.lower() for f in fs) / len(fs), 3),
            "en_otros": round(sum(f["pred"] == OTROS for f in fs) / len(fs), 3),
        }
    por_fuente = {}
    for fte in sorted({f["fuente"] for f in filas}):
        fs = [f for f in filas if f["fuente"] == fte]
        por_fuente[fte] = {"n": len(fs), "exactitud": round(sum(map(ok, fs)) / len(fs), 3)}
    confs = [f["conf"] for f in propuestas if f["conf"] is not None]
    confusion = Counter((f["real"], f["pred"]) for f in filas if not ok(f))

    fallos: Counter = Counter()
    ejemplo: dict[str, str] = {}
    for f in filas:
        if not ok(f):
            fallos[f["grupo"]] += 1
            ejemplo.setdefault(f["grupo"], f["desc"])
    return {
        "n": n,
        "exactitud_global": round(sum(map(ok, filas)) / n, 3) if n else 0,
        "cobertura_otros": round(sum(f["pred"] == OTROS for f in filas) / n, 3) if n else 0,
        "exactitud_sobre_propuestas": round(sum(map(ok, propuestas)) / len(propuestas), 3) if propuestas else 0,
        "exactitud_sin_otros_reales": round(sum(map(ok, reales_no_otros)) / len(reales_no_otros), 3) if reales_no_otros else 0,
        "confianza_media": round(sum(confs) / len(confs), 3) if confs else 0,
        "segmentos": segmentos,
        "por_categoria": por_cat,
        "por_fuente": por_fuente,
        "confusion": [(a, b, c) for (a, b), c in confusion.most_common(10)],
        "_fallos": fallos,
        "_ejemplo": ejemplo,
        "_filas": filas,
    }


def imprimir(res: dict, top: int, mostrar_errores: bool) -> dict:
    agregados = {k: v for k, v in res.items() if not k.startswith("_")}
    print(f"Movimientos confirmados evaluados: {res['n']}")
    print(f"Exactitud global: {res['exactitud_global']:.1%}")
    print(f"Cobertura: {res['cobertura_otros']:.1%} queda en «Otros» (la app preguntaría)")
    print(f"Exactitud cuando propone categoría: {res['exactitud_sobre_propuestas']:.1%}")
    print(f"Exactitud sin contar los que la persona dejó en «Otros»: {res['exactitud_sin_otros_reales']:.1%}")
    print(f"Confianza media de las propuestas: {res['confianza_media']}")
    sg = res["segmentos"]
    print(f"\nComercios (n={sg['n_comercios']}): exactitud {sg['exactitud_comercios']:.1%}, "
          f"sin contar los dejados en «Otros» {sg['exactitud_comercios_sin_otros_reales']:.1%}, "
          f"cuando propone {sg['exactitud_comercios_propuestos']:.1%}, "
          f"queda en «Otros» {sg['cobertura_otros_comercios']:.1%}")
    print(f"Transferencias entre personas (n={sg['n_personas']}): propuestas como «Transferencias» "
          f"{sg['personas_propuestas_como_transferencias']:.0%}; la persona las dejó como «Transferencias» "
          f"{sg['personas_que_la_persona_dejo_como_transferencias']:.0%} (el resto son gastos que el nombre no revela)")
    print("\nPor categoría real (n, exactitud, % que cae en Otros):")
    for cat, d in sorted(res["por_categoria"].items(), key=lambda kv: -kv[1]["n"]):
        print(f"  {cat:<28} n={d['n']:<4} exactitud={d['exactitud']:.0%}  otros={d['en_otros']:.0%}")
    print("\nPor fuente de la decisión:")
    for fte, d in res["por_fuente"].items():
        print(f"  {fte:<14} n={d['n']:<4} exactitud={d['exactitud']:.0%}")
    print("\nConfusiones más frecuentes (real -> propuesta):")
    for a, b, c in res["confusion"]:
        print(f"  {a} -> {b}: {c}")
    print(f"\nComercios que más fallan (top {top}, enmascarados salvo marcas públicas):")
    for grupo, c in res["_fallos"].most_common(top):
        print(f"  {enmascarar(grupo, res['_ejemplo'][grupo])}: {c}")
    if mostrar_errores:
        print("\n[LOCAL] Errores con descripción cruda:")
        for f in res["_filas"]:
            if f["real"].lower() != f["pred"].lower():
                print(f"  real={f['real']} pred={f['pred']} ({f['fuente']}) :: {f['desc']}")
    return agregados


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ruta")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--min-confianza", type=float, default=None, help="umbral del modelo aprendido (por defecto el de producción)")
    ap.add_argument("--modo", choices=["comercio", "movimiento"], default="comercio",
                    help="comercio: deja fuera todo el comercio (comercios nuevos); movimiento: solo el evaluado (comercios repetidos)")
    ap.add_argument("--salida-json", help="guarda SOLO los agregados")
    ap.add_argument("--mostrar-errores", action="store_true", help="LOCAL: imprime descripciones crudas")
    a = ap.parse_args(argv)
    movs = cargar_confirmados(a.ruta)
    if not movs:
        print("No hay movimientos confirmados para evaluar.")
        return 1
    res = evaluar(movs, a.min_confianza, a.modo)
    agregados = imprimir(res, a.top, a.mostrar_errores)
    if a.salida_json:
        Path(a.salida_json).write_text(json.dumps(agregados, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
