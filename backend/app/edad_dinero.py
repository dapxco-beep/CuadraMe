"""
'Age of Money' (métrica insignia de YNAB): cuántos días, en promedio, pasa
el dinero en tus cuentas antes de gastarse. Aproximación FIFO simplificada:
cada gasto "consume" primero los ingresos más antiguos que aún no se han
agotado, y se promedia la edad de ese dinero consumido en los últimos N días.
"""
from datetime import datetime

from app.utiles import ahora_co


def calcular_edad_dinero(movimientos: list[dict], dias_ventana: int = 30, referencia: datetime | None = None) -> int:
    """movimientos: [{fecha, tipo, monto}] ordenados o no, tipo income|expense.
    Retorna la edad promedio en días del dinero gastado en los dias_ventana
    días previos a `referencia` (por defecto, hoy)."""
    ingresos = sorted(
        [{"fecha": m["fecha"], "restante": m["monto"]} for m in movimientos if m["tipo"] == "income"],
        key=lambda x: x["fecha"],
    )
    if not ingresos:
        return 0

    ref = referencia or ahora_co()
    gastos = sorted(
        [m for m in movimientos if m["tipo"] == "expense" and 0 <= (ref - m["fecha"]).days <= dias_ventana],
        key=lambda x: x["fecha"],
    )
    if not gastos:
        return 0

    edades_ponderadas = 0.0
    monto_total = 0.0
    cursor_ingreso = 0

    for gasto in gastos:
        restante_gasto = gasto["monto"]
        while restante_gasto > 0 and cursor_ingreso < len(ingresos):
            ingreso = ingresos[cursor_ingreso]
            if ingreso["fecha"] > gasto["fecha"]:
                break
            consumido = min(ingreso["restante"], restante_gasto)
            if consumido <= 0:
                cursor_ingreso += 1
                continue
            edad_dias = (gasto["fecha"] - ingreso["fecha"]).days
            edades_ponderadas += edad_dias * consumido
            monto_total += consumido
            ingreso["restante"] -= consumido
            restante_gasto -= consumido
            if ingreso["restante"] <= 0:
                cursor_ingreso += 1

    if monto_total == 0:
        return 0
    return round(edades_ponderadas / monto_total)


def tendencia_edad(edad_actual: int, edad_anterior: int) -> str:
    if edad_actual > edad_anterior + 2:
        return "subiendo"
    if edad_actual < edad_anterior - 2:
        return "bajando"
    return "estable"


def mensaje_edad(edad: int, tendencia: str) -> str:
    if edad == 0:
        return "Aún no hay suficiente historial para calcular esto."
    base = f"Tu dinero dura en promedio {edad} días antes de gastarse."
    if tendencia == "subiendo":
        return base + " Vas mejorando tu colchón."
    if tendencia == "bajando":
        return base + " Está bajando, vale la pena revisar tus gastos."
    return base + " Se mantiene estable."
