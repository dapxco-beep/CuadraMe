"""
Cálculos de tarjetas de crédito reales (cuentas de tipo "credito").

Convención de saldo: igual que en cualquier cuenta, un gasto RESTA. Una tarjeta
con saldo -800.000 significa que se han usado 800.000 del cupo. Un saldo >= 0
significa cupo usado = 0 (si pagaste de más queda a favor, no se considera
cupo extra).

Funciones puras: reciben `hoy` para poder probarlas con fechas fijas.
"""
import calendar
from datetime import date, datetime

from app.utiles import ahora_co

UMBRAL_ALERTA = 30  # % de utilización a partir del cual conviene vigilar
UMBRAL_CRITICO = 80  # % que ya afecta el score crediticio y deja poco margen
PCT_PAGO_MINIMO = 0.05  # estimación: 5% del saldo usado + intereses (cada banco difiere)
DIAS_AVISO_PAGO = 3  # cuántos días antes del pago se avisa por push


def _fecha_en_mes(anio: int, mes: int, dia: int) -> date:
    """Clampa el día al último día real del mes (31 en febrero -> 28/29)."""
    return date(anio, mes, min(dia, calendar.monthrange(anio, mes)[1]))


def proxima_fecha(dia: int, hoy: date) -> date:
    """Próxima ocurrencia (hoy incluido) de un 'día del mes'."""
    f = _fecha_en_mes(hoy.year, hoy.month, dia)
    if f >= hoy:
        return f
    anio, mes = (hoy.year + 1, 1) if hoy.month == 12 else (hoy.year, hoy.month + 1)
    return _fecha_en_mes(anio, mes, dia)


def nivel_utilizacion(pct: float | None) -> str:
    if pct is None:
        return "sin_cupo"
    if pct > UMBRAL_CRITICO:
        return "critico"
    if pct > UMBRAL_ALERTA:
        return "alerta"
    return "ok"


def calc_tarjeta(cuenta, hoy: datetime | None = None) -> dict:
    """Devuelve cupo usado/disponible, % de utilización, próximas fechas de
    corte y pago (hora Colombia), pago mínimo e interés estimados."""
    hoy_d = (hoy or ahora_co()).date()
    usado = max(0.0, -(cuenta.saldo or 0))
    cupo = cuenta.cupo_total if cuenta.cupo_total and cuenta.cupo_total > 0 else None

    disponible = max(0.0, cupo - usado) if cupo else None
    pct = round(usado / cupo * 100, 1) if cupo else None

    corte = proxima_fecha(cuenta.dia_corte, hoy_d) if cuenta.dia_corte else None
    pago = proxima_fecha(cuenta.dia_pago, hoy_d) if cuenta.dia_pago else None

    # Interés de un mes si NO se paga el total: la tasa efectiva anual se
    # convierte a mensual equivalente (1+ea)^(1/12)-1, no ea/12.
    interes = None
    if cuenta.tasa_ea is not None:
        tasa_mensual = (1 + cuenta.tasa_ea / 100) ** (1 / 12) - 1
        interes = round(usado * tasa_mensual)
    minimo = min(usado, usado * PCT_PAGO_MINIMO + (interes or 0))

    return {
        "cupo_usado": round(usado),
        "cupo_disponible": round(disponible) if disponible is not None else None,
        "utilizacion_pct": pct,
        "nivel_utilizacion": nivel_utilizacion(pct),
        "proximo_corte": corte.isoformat() if corte else None,
        "proximo_pago": pago.isoformat() if pago else None,
        "dias_para_corte": (corte - hoy_d).days if corte else None,
        "dias_para_pago": (pago - hoy_d).days if pago else None,
        "pago_minimo_estimado": round(minimo),
        "interes_estimado": interes,
    }


def tarjetas_por_avisar(cuentas, hoy: datetime | None = None):
    """Filtra las tarjetas a las que hoy toca avisar 'paga antes del X':
    tienen deuda, su pago es en <= DIAS_AVISO_PAGO días y ese pago aún no se
    avisó (ultima_alerta_pago guarda la fecha de pago ya notificada, así el
    cron diario no repite el mismo aviso). Devuelve [(cuenta, info)]."""
    por_avisar = []
    for c in cuentas:
        if c.tipo != "credito" or not c.dia_pago:
            continue
        info = calc_tarjeta(c, hoy)
        if info["cupo_usado"] <= 0:
            continue
        if info["dias_para_pago"] > DIAS_AVISO_PAGO:
            continue
        if c.ultima_alerta_pago == info["proximo_pago"]:
            continue
        por_avisar.append((c, info))
    return por_avisar
