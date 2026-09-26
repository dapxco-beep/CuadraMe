"""Health score y reporte mensual. Migrado de Operations.js (calcHealthScore_, generarReporteMensual)."""


def calc_health_score(ingresos: float, gastos: float, ahorro: float, num_movimientos: int) -> dict:
    score = 0
    tips = []

    tasa_ahorro = ahorro / ingresos if ingresos > 0 else 0
    if tasa_ahorro >= 0.3:
        score += 40
    elif tasa_ahorro >= 0.2:
        score += 30
        tips.append("Meta: ahorrar al menos 30% de tus ingresos")
    elif tasa_ahorro >= 0.1:
        score += 20
        tips.append("Intenta reducir gastos para llegar al 20% de ahorro")
    elif tasa_ahorro > 0:
        score += 10
        tips.append("Tu tasa de ahorro es muy baja, revisa tus gastos fijos")
    else:
        tips.append("¡Tus gastos superan tus ingresos! Revisa urgente")

    burn_rate = gastos / ingresos if ingresos > 0 else 1
    if burn_rate <= 0.5:
        score += 30
    elif burn_rate <= 0.7:
        score += 20
    elif burn_rate <= 0.9:
        score += 10
        tips.append("Tu burn rate es alto, considera reducir gastos variables")
    else:
        tips.append("Burn rate crítico: estás usando más del 90% de tus ingresos")

    score += 20  # diversificación de categorías, simplificado

    if num_movimientos >= 20:
        score += 10
    elif num_movimientos >= 10:
        score += 7
    elif num_movimientos >= 5:
        score += 4
        tips.append("Registra más transacciones para mejores insights")
    else:
        tips.append("Necesitas registrar más transacciones")

    if not tips:
        tips.append("¡Excelente! Tus finanzas están en muy buen estado")

    return {"score": min(100, round(score)), "tips": tips, "tasa_ahorro": round(tasa_ahorro * 100, 1)}


def detectar_duplicados(movimientos: list[dict], dias_ventana: int = 3) -> list[dict]:
    ventana_ms = dias_ventana * 86400
    dups = []
    for i in range(len(movimientos)):
        for j in range(i + 1, len(movimientos)):
            a, b = movimientos[i], movimientos[j]
            time_diff = abs((a["fecha"] - b["fecha"]).total_seconds())
            same_amt = abs(a["monto"] - b["monto"]) < 1
            same_cat = a["categoria"] == b["categoria"]
            if time_diff <= ventana_ms and same_amt and same_cat:
                dups.append({"a": a["id"], "b": b["id"], "monto": a["monto"]})
        if len(dups) > 20:
            break
    return dups
