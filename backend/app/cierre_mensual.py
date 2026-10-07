"""
Cierre financiero mensual. Función PURA: recibe los movimientos del mes y del mes
anterior ya en COP y con su tipo EFECTIVO (sin pagos de tarjeta ni traslados
propios, ver contabilidad.py) y devuelve el informe. Sin BD, sin red, sin reloj.
"""
from app.contabilidad import es_interes

MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
            "septiembre", "octubre", "noviembre", "diciembre"]

UMBRAL_ALZA_PCT = 20          # una categoría "subió" de verdad si crece >= 20 % ...
UMBRAL_ALZA_MIN = 30_000      # ... y al menos 30.000 COP (evita alarmas por centavos)
META_AHORRO_PCT = 10          # por debajo de 10 % de ahorro se sugiere apartar


def nombre_mes(mes: str) -> str:
    anio, num = mes.split("-")
    return f"{MESES_ES[int(num) - 1]} de {anio}"


def _pesos(v: float) -> str:
    return "$" + f"{round(v):,.0f}".replace(",", ".")


def _gastos_por_categoria(movs: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for m in movs:
        if m["tipo"] == "expense":
            out[m["categoria"]] = out.get(m["categoria"], 0.0) + m["monto"]
    return out


def categoria_que_mas_subio(actual: dict[str, float], anterior: dict[str, float]) -> dict | None:
    """Mayor aumento ABSOLUTO frente al mes anterior. Una categoría nueva (sin gasto previo) cuenta
    como aumento con variación indefinida (None), no infinita."""
    mejor = None
    for cat, monto in actual.items():
        previo = anterior.get(cat, 0.0)
        alza = monto - previo
        if alza < UMBRAL_ALZA_MIN:
            continue
        pct = round(alza / previo * 100, 1) if previo > 0 else None
        if pct is not None and pct < UMBRAL_ALZA_PCT:
            continue
        if mejor is None or alza > mejor["aumento"]:
            mejor = {"categoria": cat, "monto": round(monto), "monto_anterior": round(previo),
                     "aumento": round(alza), "variacion_pct": pct}
    return mejor


def proximas_acciones(r: dict) -> list[str]:
    """1-2 acciones concretas, en orden de prioridad."""
    acciones: list[str] = []
    if r["ingresos"] > 0 and r["gastos"] > r["ingresos"]:
        top = r["top_categorias"][0]["categoria"] if r["top_categorias"] else "tus gastos"
        acciones.append(
            f"Gastaste {_pesos(r['gastos'] - r['ingresos'])} más de lo que ingresó: ponle un tope a {top} el próximo mes."
        )
    alza = r["categoria_que_mas_subio"]
    if alza:
        cuanto = f"subió {alza['variacion_pct']:g} %" if alza["variacion_pct"] is not None else "es nueva en tus gastos"
        acciones.append(f"{alza['categoria']} {cuanto} (+{_pesos(alza['aumento'])}): revísala y crea un presupuesto.")
    if r["intereses_pagados"] > 0:
        acciones.append(
            f"Pagaste {_pesos(r['intereses_pagados'])} en intereses: si te sobra algo, abona extra a la deuda de mayor tasa."
        )
    if r["ingresos"] > 0 and 0 <= r["tasa_ahorro"] < META_AHORRO_PCT and r["gastos"] <= r["ingresos"]:
        acciones.append(
            f"Aparta {_pesos(r['ingresos'] * META_AHORRO_PCT / 100)} ({META_AHORRO_PCT} % de tus ingresos) apenas te llegue el primer ingreso."
        )
    if r["ingresos"] > 0 and r["tasa_ahorro"] >= 20:
        acciones.append(f"Buen mes: ahorraste {_pesos(r['ahorro'])}. Muévelo a una meta o inversión antes de gastarlo.")
    if not acciones:
        acciones.append("Sigue registrando tus movimientos: con más datos el cierre te dará recomendaciones más precisas.")
    return acciones[:2]


def generar_cierre(
    mes: str,
    movs_mes: list[dict],
    movs_anterior: list[dict],
    intereses_estimados_deudas: float = 0.0,
    patrimonio_inicio: float | None = None,
    patrimonio_fin: float | None = None,
) -> dict:
    """movs_*: [{tipo ('income'|'expense'), monto (COP), categoria, descripcion}] con tipo efectivo."""
    ingresos = sum(m["monto"] for m in movs_mes if m["tipo"] == "income")
    gastos = sum(m["monto"] for m in movs_mes if m["tipo"] == "expense")
    ahorro = ingresos - gastos
    tasa = round(ahorro / ingresos * 100, 1) if ingresos > 0 else 0.0

    actual = _gastos_por_categoria(movs_mes)
    anterior = _gastos_por_categoria(movs_anterior)
    top = sorted(({"categoria": k, "monto": round(v)} for k, v in actual.items()), key=lambda x: -x["monto"])[:3]

    intereses = sum(
        m["monto"] for m in movs_mes
        if m["tipo"] == "expense" and es_interes(m.get("categoria", ""), m.get("descripcion", ""))
    )

    patrimonio = None
    if patrimonio_fin is not None:
        patrimonio = {
            "inicio": round(patrimonio_inicio) if patrimonio_inicio is not None else None,
            "fin": round(patrimonio_fin),
            "variacion": round(patrimonio_fin - patrimonio_inicio) if patrimonio_inicio is not None else None,
        }

    informe = {
        "mes": mes,
        "titulo": f"Cierre de {nombre_mes(mes)}",
        "sin_datos": not movs_mes,
        "ingresos": round(ingresos),
        "gastos": round(gastos),
        "ahorro": round(ahorro),
        "tasa_ahorro": tasa,
        "gasto_mes_anterior": round(sum(anterior.values())),
        "top_categorias": top,
        "categoria_que_mas_subio": categoria_que_mas_subio(actual, anterior),
        "intereses_pagados": round(intereses),
        "intereses_estimados_deudas": round(intereses_estimados_deudas),
        "patrimonio": patrimonio,
        "num_movimientos": len(movs_mes),
    }
    informe["acciones"] = proximas_acciones(informe)
    informe["resumen_corto"] = (
        f"Ingresaste {_pesos(ingresos)}, gastaste {_pesos(gastos)} y "
        + (f"ahorraste {_pesos(ahorro)}" if ahorro >= 0 else f"te pasaste {_pesos(-ahorro)}")
        + "."
    )
    return informe
