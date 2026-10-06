"""
Cálculos financieros PUROS del módulo Patrimonio (sin base de datos ni red).
Están aparte del router para poder probarlos con casos numéricos verificados
a mano. Convención de fechas: días reales / 365 (Act/365), la misma que usa
Excel en XIRR/XNPV.
"""
from datetime import datetime
from typing import Optional

DIAS_ANIO = 365.0
CLASES_MERCADO = ("fondo", "etf", "accion", "cripto")
CLASES_BIEN = ("inmueble", "vehiculo")
CLASES = ("cdt",) + CLASES_MERCADO + CLASES_BIEN


def _dias(desde: datetime, hasta: datetime) -> float:
    return (hasta - desde).total_seconds() / 86400.0


def valor_cdt(capital: float, tasa_ea: float, fecha_inicio: datetime,
              fecha_ref: datetime, fecha_vencimiento: Optional[datetime] = None) -> float:
    """Valor de un CDT a `fecha_ref` con interés compuesto efectivo anual:
    capital * (1 + EA)^(días/365). La tasa viene en % (12 = 12 % E.A.).
    Antes del inicio vale el capital; después del vencimiento el valor se
    congela (el CDT ya pagó, no sigue generando intereses)."""
    if fecha_vencimiento is not None and fecha_ref > fecha_vencimiento:
        fecha_ref = fecha_vencimiento
    dias = max(0.0, _dias(fecha_inicio, fecha_ref))
    return capital * (1 + tasa_ea / 100.0) ** (dias / DIAS_ANIO)


def valor_posicion(unidades: float, precio: float) -> float:
    return unidades * precio


def rentabilidad(valor_actual: float, costo: float) -> dict:
    """Ganancia absoluta y % sobre el costo. Sin costo, el % es None."""
    ganancia = valor_actual - costo
    pct = (ganancia / costo * 100.0) if costo else None
    return {"ganancia": ganancia, "rentabilidad_pct": pct}


def xnpv(tasa: float, flujos: list) -> Optional[float]:
    """VPN con fechas irregulares. None si la cuenta se desborda (tasas enormes con
    flujos de décadas) o la tasa hace 1+tasa = 0."""
    t0 = min(f for f, _ in flujos)
    try:
        return sum(m / (1 + tasa) ** (_dias(t0, f) / DIAS_ANIO) for f, m in flujos)
    except (OverflowError, ZeroDivisionError):
        return None


def xirr(flujos: list) -> Optional[float]:
    """TIR efectiva anual de flujos [(fecha, monto)] con fechas irregulares (como
    XIRR de Excel), en fracción (0.10 = 10 %). None si no tiene solución (todos
    del mismo signo, un solo flujo o ventana menor a 1 día). Usa bisección: más
    lenta que Newton pero no diverge, y sobra para esta escala."""
    if len(flujos) < 2:
        return None
    if not (any(m > 0 for _, m in flujos) and any(m < 0 for _, m in flujos)):
        return None
    if _dias(min(f for f, _ in flujos), max(f for f, _ in flujos)) < 1:
        return None

    bajo, alto = -0.9999, 1.0
    f_bajo = xnpv(bajo, flujos)
    f_alto = xnpv(alto, flujos)
    if f_bajo is None or f_alto is None:
        return None
    while f_bajo * f_alto > 0 and alto < 1e6:  # rendimientos enormes: ampliar el techo
        alto *= 10
        f_alto = xnpv(alto, flujos)
        if f_alto is None:  # desbordó: sin solución numérica
            return None
    if f_bajo * f_alto > 0:
        return None
    for _ in range(300):
        medio = (bajo + alto) / 2
        f_medio = xnpv(medio, flujos)
        if f_medio is None:
            return None
        if abs(f_medio) < 1e-9 or (alto - bajo) < 1e-13:
            return medio
        if f_bajo * f_medio < 0:
            alto = medio
        else:
            bajo, f_bajo = medio, f_medio
    return (bajo + alto) / 2


def distribucion(valores_por_clase: dict) -> list:
    """[{clase, valor, pct}] de mayor a menor. Ignora valores <= 0 (un saldo
    negativo no es una porción de la dona)."""
    positivos = {c: v for c, v in valores_por_clase.items() if v and v > 0}
    total = sum(positivos.values())
    if not total:
        return []
    filas = [{"clase": c, "valor": v, "pct": v / total * 100.0} for c, v in positivos.items()]
    return sorted(filas, key=lambda f: f["valor"], reverse=True)


def patrimonio_neto(activos: float, cuentas: float, deudas: float) -> float:
    return activos + cuentas - deudas
