"""
Detección de patrones recurrentes (suscripciones, pagos fijos) a partir del
historial de movimientos. Agrupa por descripción normalizada y busca al menos
dos ocurrencias del mismo tipo separadas ~28-32 días con monto similar.
No crea recurrentes automáticamente: solo sugiere, el usuario confirma.
"""
from collections import defaultdict
from datetime import datetime

from app.conciliacion import normalize_texto

INTERVALO_MIN_DIAS = 25
INTERVALO_MAX_DIAS = 35
TOLERANCIA_MONTO = 0.1  # 10%
MIN_OCURRENCIAS = 2


def detectar_recurrentes(movimientos: list[dict]) -> list[dict]:
    """movimientos: [{id, descripcion, categoria, tipo, monto, fecha, cuenta_id}]"""
    grupos: dict[str, list[dict]] = defaultdict(list)
    for m in movimientos:
        if m["tipo"] not in ("expense", "income"):
            continue
        clave = normalize_texto(m["descripcion"])
        if not clave:
            continue
        grupos[clave].append(m)

    sugerencias = []
    for clave, items in grupos.items():
        if len(items) < MIN_OCURRENCIAS:
            continue

        items_ordenados = sorted(items, key=lambda m: m["fecha"])
        pares_validos = 0
        for i in range(1, len(items_ordenados)):
            dias = (items_ordenados[i]["fecha"] - items_ordenados[i - 1]["fecha"]).days
            monto_a = items_ordenados[i]["monto"]
            monto_b = items_ordenados[i - 1]["monto"]
            monto_ok = abs(monto_a - monto_b) <= max(monto_a, monto_b) * TOLERANCIA_MONTO
            if INTERVALO_MIN_DIAS <= dias <= INTERVALO_MAX_DIAS and monto_ok:
                pares_validos += 1

        if pares_validos == 0:
            continue

        ultimo = items_ordenados[-1]
        promedio_monto = sum(m["monto"] for m in items_ordenados) / len(items_ordenados)

        sugerencias.append({
            "descripcion": ultimo["descripcion"],
            "categoria": ultimo["categoria"],
            "tipo": ultimo["tipo"],
            "monto_promedio": round(promedio_monto, 2),
            "cuenta_id": ultimo.get("cuenta_id"),
            "dia_del_mes": ultimo["fecha"].day,
            "ocurrencias": len(items_ordenados),
            "ultima_fecha": ultimo["fecha"],
        })

    sugerencias.sort(key=lambda s: s["ocurrencias"], reverse=True)
    return sugerencias
