"""
Cálculos del asistente financiero (CuadraMe AI).

REGLA DE ORO: toda cifra que el asistente le muestra al usuario sale de aquí
(funciones PURAS, sin base de datos, sin red, sin reloj implícito: `hoy` entra
por parámetro). La IA solo redacta; si inventara un número, la validación de
`asistente.py` lo detecta y se usa la redacción determinista.

Convenciones: todo en COP; los "meses" se cuentan por calendario.
"""
import math
import statistics
from collections import defaultdict
from datetime import datetime

from app.estrategia_deudas import MAX_MESES, simular

# Tasa mensual de REFERENCIA para comparar cuotas de tarjeta (≈ 26,8 % E.A.).
# Es un supuesto explícito que se le muestra al usuario, no un dato suyo.
TASA_MENSUAL_REFERENCIA = 0.02
PLAZOS_CUOTAS = (3, 6, 12, 24)
# Colchón de emergencia que no se debe gastar: medio mes de gastos habituales.
FRACCION_COLCHON = 0.5


def meses_entre(hoy: datetime, destino: datetime) -> int:
    """Meses de calendario que faltan (mínimo 1). oct-2026 -> dic-2027 = 14."""
    return max(1, (destino.year - hoy.year) * 12 + (destino.month - hoy.month))


def cuota_con_interes(monto: float, n: int, tasa_mensual: float) -> float:
    """Cuota fija de un crédito (sistema francés). Con tasa 0 es monto / n."""
    if n <= 0:
        raise ValueError("n debe ser > 0")
    if tasa_mensual <= 0:
        return monto / n
    return monto * tasa_mensual / (1 - (1 + tasa_mensual) ** -n)


def disponible_real(ctx: dict) -> float:
    """Dinero que de verdad es tuyo hoy: saldo líquido (ahorro + efectivo)
    menos lo que ya está comprometido ESTE mes (gastos fijos que faltan, cuotas
    de deudas y tarjetas por pagar, aportes a metas)."""
    return (
        ctx.get("saldo_liquido", 0)
        - ctx.get("recurrentes_pendientes", 0)
        - ctx.get("cuotas_pendientes", 0)
        - ctx.get("aportes_metas", 0)
    )


def capacidad_ahorro(ctx: dict) -> float:
    """Lo que normalmente te sobra al mes: ingreso promedio - gasto promedio
    de los últimos meses completos. Nunca negativa."""
    return max(0.0, ctx.get("ingreso_mensual", 0) - ctx.get("gasto_mensual", 0))


def simular_compra(precio: float, ctx: dict) -> dict:
    """¿Puedo comprar algo de `precio`?

    ctx: saldo_liquido, recurrentes_pendientes, cuotas_pendientes, aportes_metas,
         ingreso_mensual, gasto_mensual (promedios de meses completos).
    Veredicto:
      - "si":       precio <= disponible_real - colchón (te queda tu colchón).
      - "ajustado": precio <= disponible_real (alcanza, pero te quedas sin colchón).
      - "no_aun":   precio > disponible_real.
    Alternativas: ahorrar N meses y comprar en cuotas (sin interés y con la
    tasa de referencia), con qué fracción de tu capacidad de ahorro se come.
    """
    if precio <= 0:
        raise ValueError("precio debe ser > 0")
    disponible = disponible_real(ctx)
    capacidad = capacidad_ahorro(ctx)
    colchon = round(ctx.get("gasto_mensual", 0) * FRACCION_COLCHON)
    usable = max(0.0, disponible - colchon)

    if precio <= usable:
        veredicto = "si"
    elif precio <= disponible:
        veredicto = "ajustado"
    else:
        veredicto = "no_aun"

    meses_ahorrando = None
    if precio <= usable:
        meses_ahorrando = 0
    elif capacidad > 0:
        meses_ahorrando = math.ceil((precio - usable) / capacidad)

    cuotas = []
    for n in PLAZOS_CUOTAS:
        sin = precio / n
        con = cuota_con_interes(precio, n, TASA_MENSUAL_REFERENCIA)
        cuotas.append({
            "plazo_meses": n,
            "cuota_sin_interes": round(sin),
            "cuota_con_interes": round(con),
            "costo_total_con_interes": round(con * n),
            "intereses_totales": round(con * n - precio),
            "cabe_en_tu_capacidad": bool(capacidad > 0 and con <= capacidad),
            "pct_de_tu_capacidad": round(con / capacidad * 100) if capacidad > 0 else None,
        })

    return {
        "precio": round(precio),
        "veredicto": veredicto,
        "disponible_real": round(disponible),
        "saldo_liquido": round(ctx.get("saldo_liquido", 0)),
        "recurrentes_pendientes": round(ctx.get("recurrentes_pendientes", 0)),
        "cuotas_pendientes": round(ctx.get("cuotas_pendientes", 0)),
        "aportes_metas": round(ctx.get("aportes_metas", 0)),
        "colchon_sugerido": colchon,
        "disponible_tras_colchon": round(usable),
        "capacidad_ahorro_mensual": round(capacidad),
        "quedaria_disponible": round(disponible - precio),
        "meses_ahorrando": meses_ahorrando,
        "cuotas": cuotas,
        "tasa_mensual_referencia_pct": round(TASA_MENSUAL_REFERENCIA * 100, 1),
    }


def plan_ahorro(objetivo: float, actual: float, fecha_objetivo: datetime, capacidad: float, hoy: datetime) -> dict:
    """Plan mensual para juntar `objetivo` antes de `fecha_objetivo`."""
    if objetivo <= 0:
        raise ValueError("objetivo debe ser > 0")
    faltante = max(0.0, objetivo - max(0.0, actual))
    meses = meses_entre(hoy, fecha_objetivo)
    aporte = math.ceil(faltante / meses)
    viable = capacidad > 0 and aporte <= capacidad
    meses_con_capacidad = math.ceil(faltante / capacidad) if capacidad > 0 and faltante > 0 else (0 if faltante == 0 else None)
    return {
        "objetivo": round(objetivo),
        "actual": round(actual),
        "faltante": round(faltante),
        "meses": meses,
        "aporte_mensual": aporte,
        "capacidad_ahorro_mensual": round(capacidad),
        "viable": bool(viable or faltante == 0),
        "pct_de_tu_capacidad": round(aporte / capacidad * 100) if capacidad > 0 else None,
        "meses_con_tu_capacidad": meses_con_capacidad,
    }


def plan_deudas(deudas: list[dict], meses_objetivo: int, capacidad: float, paso: int = 1000) -> dict:
    """Cuánto pagar EXTRA cada mes (sobre las cuotas actuales) para quedar libre
    de deudas en `meses_objetivo`, usando la estrategia avalancha ya existente.

    deudas: [{id, nombre, saldo, tasa_mensual, cuota}] (mismo formato que
    estrategia_deudas). Busca por bisección el menor extra, en múltiplos de
    `paso`, con el que la simulación termina a tiempo."""
    base = simular(deudas, 0, "sin_extra")
    total = round(sum(float(d.get("saldo") or 0) for d in deudas if (d.get("saldo") or 0) > 0))
    if total <= 0:
        return {"deuda_total": 0, "sin_deudas": True}
    meses_objetivo = max(1, min(int(meses_objetivo), MAX_MESES))

    def termina(extra: float) -> bool:
        r = simular(deudas, extra, "avalancha")
        return r["meses"] is not None and r["meses"] <= meses_objetivo

    # Con todo el saldo como extra se salda en 1 mes: es la cota superior.
    tope = math.ceil(total / paso) * paso
    lo, hi = 0, tope // paso
    while lo < hi:
        mid = (lo + hi) // 2
        if termina(mid * paso):
            hi = mid
        else:
            lo = mid + 1
    extra = lo * paso
    r = simular(deudas, extra, "avalancha")
    cuotas_actuales = round(sum(
        float(d.get("cuota") or 0) or (float(d["saldo"]) * float(d.get("tasa_mensual") or 0) / 100 + float(d["saldo"]) * 0.01)
        for d in deudas if (d.get("saldo") or 0) > 0
    ))
    return {
        "deuda_total": total,
        "meses_objetivo": meses_objetivo,
        "meses_sin_extra": base["meses"],
        "extra_mensual": extra,
        "pago_total_mensual": cuotas_actuales + extra,
        "cuotas_actuales": cuotas_actuales,
        "meses_logrados": r["meses"],
        "intereses_totales": round(r["intereses_totales"]),
        "intereses_sin_extra": round(base["intereses_totales"]) if base["meses"] is not None else None,
        "orden": r["orden"],
        "capacidad_ahorro_mensual": round(capacidad),
        "viable": bool(extra <= capacidad),
        "metodo": "avalancha",
    }


def gasto_por_categoria(movs: list[dict], anio: int, mes: int) -> list[dict]:
    """[{categoria, monto, pct}] de gastos del mes, de mayor a menor."""
    acum: dict[str, float] = defaultdict(float)
    for m in movs:
        if m["tipo"] == "expense" and m["fecha"].year == anio and m["fecha"].month == mes:
            acum[m["categoria"] or "Otros"] += m["monto"]
    total = sum(acum.values())
    filas = [
        {"categoria": c, "monto": round(v), "pct": round(v / total * 100) if total else 0}
        for c, v in acum.items()
    ]
    return sorted(filas, key=lambda f: f["monto"], reverse=True)


def gastos_atipicos(movs: list[dict], anio: int, mes: int, minimo: float = 50_000, factor: float = 3.0) -> list[dict]:
    """Gastos individuales del mes que superan `factor` veces la mediana de su
    categoría (con al menos 3 gastos previos para tener patrón)."""
    previos: dict[str, list[float]] = defaultdict(list)
    actuales = []
    for m in movs:
        if m["tipo"] != "expense":
            continue
        if (m["fecha"].year, m["fecha"].month) == (anio, mes):
            actuales.append(m)
        elif m["fecha"] < datetime(anio, mes, 1):
            previos[m["categoria"]].append(m["monto"])
    salida = []
    for m in actuales:
        hist = previos.get(m["categoria"], [])
        if len(hist) < 3 or m["monto"] < minimo:
            continue
        mediana = statistics.median(hist)
        if mediana > 0 and m["monto"] >= factor * mediana:
            salida.append({
                "categoria": m["categoria"],
                "descripcion": m.get("titulo") or m.get("descripcion", ""),
                "monto": round(m["monto"]),
                "mediana_categoria": round(mediana),
                "veces": round(m["monto"] / mediana, 1),
            })
    return sorted(salida, key=lambda x: x["monto"], reverse=True)[:5]


def suscripciones_anuales(recurrentes: list[dict]) -> dict:
    """Recurrentes de gasto activos: cuánto suman al mes y al AÑO."""
    gastos = [r for r in recurrentes if r.get("tipo", "expense") == "expense" and r.get("activo", True)]
    filas = sorted(
        ({"nombre": r["nombre"], "mensual": round(r["monto"]), "anual": round(r["monto"] * 12)} for r in gastos),
        key=lambda f: f["anual"],
        reverse=True,
    )
    return {
        "total_mensual": sum(f["mensual"] for f in filas),
        "total_anual": sum(f["anual"] for f in filas),
        "items": filas,
    }
