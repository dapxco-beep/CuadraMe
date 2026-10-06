"""
Cálculos puros de las compras a cuotas de una tarjeta (reciben `hoy`, sin base
de datos). Cada cuota se factura en un corte (primera_fecha + k meses) y se paga
en la fecha límite del extracto que la trae.
"""
from datetime import date, datetime

from app.tarjetas import _fecha_en_mes, limite_pago_del_corte, proxima_fecha
from app.utiles import ahora_co


def calcular_cuota(total: float, n: int, tasa_mensual_pct: float = 0.0) -> float:
    """Cuota fija mensual. Sin interés: total / n. Con interés: fórmula francesa
    cuota = total * i / (1 - (1+i)^-n), con i = tasa mensual en decimal.
    Ej. 1.000.000 a 12 cuotas al 2% mensual = 94.559,60 (se redondea al peso: 94.560)."""
    if n <= 0:
        raise ValueError("El número de cuotas debe ser mayor a 0")
    i = (tasa_mensual_pct or 0) / 100
    if i <= 0:
        return total / n
    return total * i / (1 - (1 + i) ** -n)


def capital_pendiente(total: float, n: int, tasa_mensual_pct: float, pagadas: int) -> float:
    """Capital que aún se debe del plan tras `pagadas` cuotas (lo que queda por
    amortizar, sin los intereses futuros)."""
    restantes = max(0, n - pagadas)
    if restantes == 0:
        return 0.0
    i = (tasa_mensual_pct or 0) / 100
    if i <= 0:
        return total * restantes / n
    cuota = calcular_cuota(total, n, tasa_mensual_pct)
    return cuota * (1 - (1 + i) ** -restantes) / i


def _sumar_meses(f: date, k: int, dia: int) -> date:
    m = f.month - 1 + k
    return _fecha_en_mes(f.year + m // 12, m % 12 + 1, dia)


def fechas_corte_cuotas(primera: date, n: int) -> list[date]:
    """Corte en que se factura cada cuota (conserva el día original: 31 -> 28 en febrero)."""
    return [_sumar_meses(primera, k, primera.day) for k in range(n)]


def fecha_pago_cuota(corte: date, dia_pago: int | None) -> date:
    """Cuándo se paga la cuota facturada en `corte`: la fecha límite de ese extracto
    (sin día de pago conocido, se toma el propio corte)."""
    return limite_pago_del_corte(corte, dia_pago) if dia_pago else corte


def primera_fecha_por_defecto(dia_corte: int | None, hoy: date) -> date:
    """La primera cuota cae en el próximo corte (si no hay día de corte, en un mes)."""
    if dia_corte:
        return proxima_fecha(dia_corte, hoy)
    return _sumar_meses(hoy, 1, hoy.day)


def _a_fecha(f) -> date:
    return f.date() if isinstance(f, datetime) else f


def estado_plan(total: float, n: int, cuota: float, tasa: float, pagadas_manual: int,
                primera, hoy: date, dia_pago: int | None = None) -> dict:
    """Dónde va un plan de cuotas hoy. Una cuota se considera pagada cuando se
    marcó a mano o cuando ya pasó su fecha de pago (lo que ocurra primero).

    Devuelve: pagadas, numero_actual ("va en 3 de 12"), pendientes, terminado,
    saldo_pendiente (capital), por_pagar (cuotas restantes x cuota), proxima_fecha_pago,
    termina_en ("AAAA-MM", mes de la última cuota) y vence_este_mes (la siguiente
    cuota por pagar vence en este mes o ya está atrasada)."""
    cortes = fechas_corte_cuotas(_a_fecha(primera), n)
    pagos = [fecha_pago_cuota(c, dia_pago) for c in cortes]
    automaticas = sum(1 for p in pagos if p < hoy)
    pagadas = min(n, max(pagadas_manual or 0, automaticas))
    terminado = pagadas >= n
    siguiente = None if terminado else pagos[pagadas]
    fin_de_mes = _fecha_en_mes(hoy.year, hoy.month, 31)
    return {
        "pagadas": pagadas,
        "numero_actual": min(n, pagadas + 1),
        "pendientes": n - pagadas,
        "terminado": terminado,
        "saldo_pendiente": round(capital_pendiente(total, n, tasa, pagadas)),
        "por_pagar": round(cuota * (n - pagadas)),
        "proxima_fecha_pago": siguiente.isoformat() if siguiente else None,
        "termina_en": f"{pagos[-1].year}-{pagos[-1].month:02d}",
        "vence_este_mes": bool(siguiente and siguiente <= fin_de_mes),
    }


def cuota_en_mes(n: int, cuota: float, pagadas: int, primera, anio: int, mes: int,
                 dia_pago: int | None = None) -> float:
    """Lo que vence en el mes (anio, mes) de un plan: las cuotas aún no pagadas cuya
    fecha de pago cae en ese mes (`pagadas` = las ya pagadas hoy, ver estado_plan)."""
    cortes = fechas_corte_cuotas(_a_fecha(primera), n)
    total = 0.0
    for k in range(pagadas, n):
        p = fecha_pago_cuota(cortes[k], dia_pago)
        if (p.year, p.month) == (anio, mes):
            total += cuota
    return total


def hoy_co() -> date:
    return ahora_co().date()
