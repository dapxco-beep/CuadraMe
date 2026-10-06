"""
Resumen mensual tipo "Wrapped". Función PURA: recibe los movimientos del mes y
del mes anterior (ya en COP) y devuelve los datos de las diapositivas.
Solo usa datos del propio usuario.
"""
from datetime import date, timedelta


def mejor_racha(fechas: list[date]) -> int:
    """Mayor cantidad de días consecutivos con al menos un movimiento."""
    dias = sorted(set(fechas))
    mejor = actual = 0
    previo = None
    for d in dias:
        actual = actual + 1 if previo is not None and d - previo == timedelta(days=1) else 1
        mejor = max(mejor, actual)
        previo = d
    return mejor


def _totales(movs: list[dict]) -> tuple[float, float]:
    ingresos = sum(m["monto"] for m in movs if m["tipo"] == "income")
    gastos = sum(m["monto"] for m in movs if m["tipo"] == "expense")
    return ingresos, gastos


MAX_CATEGORIAS = 7


def _desglose(actual: dict[str, float], anterior: dict[str, float], total: float) -> list[dict]:
    """Gasto por categoría, de mayor a menor: monto, % del total y cambio frente al mes
    anterior (None si ese mes no tuvo gasto en la categoría, porque un % sobre cero no
    dice nada). Las categorías pequeñas se agrupan en 'Otras' para que la lista quepa."""
    filas = sorted(actual.items(), key=lambda kv: kv[1], reverse=True)
    visibles, resto = filas[:MAX_CATEGORIAS], filas[MAX_CATEGORIAS:]
    salida = []
    for nombre, monto in visibles:
        ant = anterior.get(nombre, 0.0)
        salida.append({
            "categoria": nombre,
            "monto": monto,
            "pct": round(monto / total * 100, 1) if total > 0 else 0.0,
            "monto_anterior": ant,
            "variacion_pct": round((monto - ant) / ant * 100, 1) if ant > 0 else None,
        })
    if resto:
        monto = sum(m for _, m in resto)
        ant = sum(anterior.get(n, 0.0) for n, _ in resto)
        salida.append({
            "categoria": "Otras",
            "monto": monto,
            "pct": round(monto / total * 100, 1) if total > 0 else 0.0,
            "monto_anterior": ant,
            "variacion_pct": round((monto - ant) / ant * 100, 1) if ant > 0 else None,
        })
    return salida


def calcular_wrapped(mes: str, movs_mes: list[dict], movs_anterior: list[dict]) -> dict:
    """Cada movimiento: {tipo, monto, categoria, fecha(datetime|date)}."""
    ingresos, gastos = _totales(movs_mes)
    _, gastos_ant = _totales(movs_anterior)

    por_categoria: dict[str, float] = {}
    for m in movs_mes:
        if m["tipo"] == "expense":
            por_categoria[m["categoria"]] = por_categoria.get(m["categoria"], 0) + m["monto"]
    top = max(por_categoria.items(), key=lambda kv: kv[1], default=None)
    por_categoria_ant: dict[str, float] = {}
    for m in movs_anterior:
        if m["tipo"] == "expense":
            por_categoria_ant[m["categoria"]] = por_categoria_ant.get(m["categoria"], 0) + m["monto"]
    categorias = _desglose(por_categoria, por_categoria_ant, gastos)

    if gastos_ant > 0:
        variacion = round((gastos - gastos_ant) / gastos_ant * 100, 1)
    else:
        variacion = None  # sin mes anterior no hay comparación honesta

    fechas = [m["fecha"].date() if hasattr(m["fecha"], "date") else m["fecha"] for m in movs_mes]
    return {
        "mes": mes,
        "gasto_total": gastos,
        "ingresos": ingresos,
        "ahorro": ingresos - gastos,
        "tasa_ahorro": round((ingresos - gastos) / ingresos * 100, 1) if ingresos > 0 else 0.0,
        "categoria_top": {"categoria": top[0], "monto": top[1]} if top else None,
        "categorias": categorias,
        "mejor_racha": mejor_racha(fechas),
        "num_movimientos": len(movs_mes),
        "gasto_mes_anterior": gastos_ant,
        "variacion_gasto_pct": variacion,
    }
