"""
Alertas proactivas al estilo Fintonic: el elogio #1 en reseñas reales de
usuarios de apps de finanzas es "me avisó de algo que no sabía que tenía"
(comisiones, cobros duplicados). Esta detección es puramente basada en
reglas sobre datos ya existentes — no depende de IA ni de conexión bancaria.
"""
import re
from collections import defaultdict
from datetime import timedelta

from app.utiles import ahora_co

PATRON_COMISION = re.compile(
    r"comisi[oó]n|cuota\s+de\s+manejo|manejo\s+de\s+cuenta|cargo\s+por\s+servicio|gmf|4x1000|cuatro\s+por\s+mil",
    re.IGNORECASE,
)


def detectar_comisiones(movimientos: list[dict]) -> list[dict]:
    """movimientos: [{id, descripcion, monto, fecha, tipo}]. Agrupa gastos que
    matchean patrones de comisión bancaria por descripción normalizada, para
    mostrar cuánto se ha ido en comisiones este mes y el histórico."""
    hoy = ahora_co()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    comisiones_mes = [
        m for m in movimientos
        if m["tipo"] == "expense" and m["fecha"] >= inicio_mes and PATRON_COMISION.search(m["descripcion"])
    ]
    if not comisiones_mes:
        return []

    por_descripcion: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "veces": 0})
    for m in comisiones_mes:
        clave = m["descripcion"].strip().lower()[:40]
        por_descripcion[clave]["total"] += m["monto"]
        por_descripcion[clave]["veces"] += 1
        por_descripcion[clave]["descripcion"] = m["descripcion"]

    return [
        {"descripcion": v["descripcion"], "total_mes": round(v["total"]), "veces": v["veces"]}
        for v in por_descripcion.values()
    ]


def detectar_cobros_duplicados(movimientos: list[dict]) -> list[dict]:
    """Dos gastos con la MISMA descripción normalizada y el MISMO monto
    exacto, en una ventana de 48 horas — señal fuerte de cobro duplicado
    (ej. un comercio que procesó el pago dos veces por error)."""
    candidatos = [m for m in movimientos if m["tipo"] == "expense"]
    candidatos.sort(key=lambda m: m["fecha"])

    duplicados = []
    vistos = set()

    for i, a in enumerate(candidatos):
        if a["id"] in vistos:
            continue
        clave_a = (a["descripcion"].strip().lower(), round(a["monto"], 2))
        for b in candidatos[i + 1:]:
            if (b["fecha"] - a["fecha"]) > timedelta(hours=48):
                break
            clave_b = (b["descripcion"].strip().lower(), round(b["monto"], 2))
            if clave_a == clave_b and b["id"] not in vistos:
                duplicados.append({
                    "descripcion": a["descripcion"],
                    "monto": a["monto"],
                    "fecha_1": a["fecha"],
                    "fecha_2": b["fecha"],
                    "movimiento_id_1": a["id"],
                    "movimiento_id_2": b["id"],
                })
                vistos.add(a["id"])
                vistos.add(b["id"])
                break

    return duplicados
