"""
Informes > Resumen: flujo neto, ingresos por fuente, presupuesto contra gasto real y hallazgos.

Todo son funciones puras sobre los movimientos "efectivos" (regla única de contabilidad.py: los traslados entre tus
cuentas, pagos de tarjeta y ajustes ya vienen como 'transfer' y no suman). Los totales, la comparación contra el
periodo anterior y la serie mensual con tasa de ahorro NO se recalculan aquí: salen de `informe.ingresos_gastos`,
para que el Resumen y el resto de Informes cuenten exactamente igual.
"""
import bisect
import calendar
from datetime import datetime, timedelta

from app import informe as inf
from app import planificacion as plan

MAX_PUNTOS = 120          # más barras que esto no se leen en un teléfono: se agrupa más grueso
MAX_FUENTES = 6
UMBRAL_CAMBIO_PCT = 10    # variaciones menores no se cuentan como noticia
UMBRAL_PESO_CATEGORIA = 25


# ── Flujo neto ──────────────────────────────────────────────────────────────────────────────
def agrupacion_auto(rango: dict) -> str:
    dias = (rango["hasta"] - rango["desde"]).days
    return "dia" if dias <= 31 else "semana" if dias <= 140 else "mes"


def _cubetas(rango: dict, agrupar: str) -> list[tuple[datetime, datetime]]:
    """[(desde, hasta_exclusivo)] recortadas al rango: días, semanas lunes-domingo o meses calendario."""
    d0, h0 = rango["desde"], rango["hasta"]
    out: list[tuple[datetime, datetime]] = []
    if agrupar == "dia":
        cur = d0
        while cur < h0:
            out.append((cur, cur + timedelta(days=1)))
            cur += timedelta(days=1)
    elif agrupar == "semana":
        cur = d0
        while cur < h0:
            fin = cur + timedelta(days=7 - cur.weekday())  # hasta el próximo lunes
            out.append((cur, min(fin, h0)))
            cur = fin
    else:
        cur = d0
        while cur < h0:
            fin = inf.inicio_mes(*inf.sumar_meses(cur.year, cur.month, 1))
            out.append((cur, min(fin, h0)))
            cur = fin
    return out


def _etiquetas(d: datetime, h: datetime, agrupar: str) -> tuple[str, str]:
    ultimo = h - timedelta(days=1)
    corto = inf.MESES_CORTOS
    if agrupar == "dia":
        return str(d.day), f"{d.day} de {inf.MESES[d.month - 1]}"
    if agrupar == "semana":
        return f"{d.day} {corto[d.month - 1]}", f"del {d.day} de {inf.MESES[d.month - 1]} al {ultimo.day} de {inf.MESES[ultimo.month - 1]}"
    return corto[d.month - 1].capitalize(), f"{inf.MESES[d.month - 1]} de {d.year}"


def flujo_neto(movs: list[dict], rango: dict, agrupar: str | None = None) -> dict:
    """Ingresos, gastos y flujo neto (ingresos − gastos) por día, semana o mes DENTRO del rango, más el acumulado.
    Un tramo sin ningún movimiento va con `con_datos: false` y valores None (hueco, no un cero engañoso)."""
    agrupar = agrupar if agrupar in ("dia", "semana", "mes") else agrupacion_auto(rango)
    cubetas = _cubetas(rango, agrupar)
    # Si salen demasiadas barras se pasa a una agrupación más gruesa en vez de dibujar ruido.
    while len(cubetas) > MAX_PUNTOS and agrupar != "mes":
        agrupar = "semana" if agrupar == "dia" else "mes"
        cubetas = _cubetas(rango, agrupar)
    sumas = [[0.0, 0.0, 0] for _ in cubetas]
    inicios = [c[0] for c in cubetas]
    for m in movs:
        if m["tipo"] not in ("income", "expense") or not inf.en_rango(m, rango):
            continue
        i = bisect.bisect_right(inicios, m["fecha"]) - 1
        if i < 0:
            continue
        s = sumas[i]
        s[0 if m["tipo"] == "income" else 1] += m["monto"]
        s[2] += 1
    puntos, acum = [], 0
    for (d, h), (ing, gas, n) in zip(cubetas, sumas):
        con = n > 0
        neto = round(ing) - round(gas)
        if con:
            acum += neto
        corta, larga = _etiquetas(d, h, agrupar)
        puntos.append({
            "clave": d.date().isoformat(), "etiqueta": corta, "etiqueta_larga": larga,
            "desde": d.date().isoformat(), "hasta": (h - timedelta(days=1)).date().isoformat(),
            "ingresos": round(ing) if con else None, "gastos": round(gas) if con else None,
            "neto": neto if con else None, "acumulado": acum, "con_datos": con,
        })
    con_datos = [p for p in puntos if p["con_datos"]]
    return {
        "agrupar": agrupar,
        "puntos": puntos,
        "positivos": sum(1 for p in con_datos if p["neto"] > 0),
        "negativos": sum(1 for p in con_datos if p["neto"] < 0),
        "mejor": max(con_datos, key=lambda p: p["neto"])["clave"] if con_datos else None,
        "peor": min(con_datos, key=lambda p: p["neto"])["clave"] if con_datos else None,
        "hay_datos": bool(con_datos),
    }


def meses_de_la_serie(rango: dict) -> int:
    """Cuántos meses mostrar en la evolución de la tasa de ahorro: los que cubre el rango, mínimo 6 (para tener
    contexto en periodos cortos) y máximo 24."""
    ultimo = rango["hasta"] - timedelta(days=1)
    cubre = (ultimo.year - rango["desde"].year) * 12 + ultimo.month - rango["desde"].month + 1
    return max(6, min(24, cubre))


# ── Ingresos por fuente ─────────────────────────────────────────────────────────────────────
def _ingresos_por_fuente(movs: list[dict], rango: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in movs:
        if m["tipo"] != "income" or not inf.en_rango(m, rango):
            continue
        nombre = (m.get("titulo") or m.get("descripcion") or "").strip()
        clave = inf.clave_comercio(m.get("descripcion", "")) or inf.clave_comercio(m.get("categoria") or "Otros")
        f = out.setdefault(clave, {"nombre": nombre or (m.get("categoria") or "Otros"), "monto": 0.0, "num": 0,
                                   "categoria": m.get("categoria") or "Otros"})
        f["monto"] += m["monto"]
        f["num"] += 1
    return out


def ingresos_por_fuente(movs: list[dict], rango: dict, anterior: dict, maximo: int = MAX_FUENTES) -> dict:
    """De dónde entra la plata: las fuentes más grandes del periodo (agrupadas por el texto del banco) y el resto
    junto en «Otras fuentes». Cada fuente trae su cambio contra el periodo anterior (None sin base)."""
    actual = _ingresos_por_fuente(movs, rango)
    previo = _ingresos_por_fuente(movs, anterior)
    total = sum(f["monto"] for f in actual.values())
    orden = sorted(actual.items(), key=lambda kv: kv[1]["monto"], reverse=True)
    fuentes = []
    for clave, f in orden[:maximo]:
        prev = previo.get(clave, {"monto": 0.0})["monto"]
        fuentes.append({
            "clave": clave, "nombre": f["nombre"][:60], "categoria": f["categoria"], "monto": round(f["monto"]),
            "pct": inf._pct(f["monto"], total), "num": f["num"],
            "anterior": round(prev), "variacion_pct": inf._variacion(f["monto"], prev),
        })
    resto = orden[maximo:]
    otras = None
    if resto:
        monto = sum(f["monto"] for _, f in resto)
        otras = {"cantidad": len(resto), "monto": round(monto), "pct": inf._pct(monto, total),
                 "num": sum(f["num"] for _, f in resto)}
    return {"total": round(total), "fuentes": fuentes, "otras": otras, "hay_datos": bool(actual)}


# ── Presupuesto contra gasto real ───────────────────────────────────────────────────────────
def _fraccion_de_meses(rango: dict) -> float:
    """Cuántos «meses de presupuesto» cubre el rango: cada mes aporta (días del rango en ese mes / días del mes)."""
    total, cur = 0.0, rango["desde"]
    while cur < rango["hasta"]:
        fin = inf.inicio_mes(*inf.sumar_meses(cur.year, cur.month, 1))
        tramo = (min(fin, rango["hasta"]) - cur).days
        total += tramo / calendar.monthrange(cur.year, cur.month)[1]
        cur = fin
    return total


def _limite_mensual(limite: float, periodo: str | None) -> float:
    """Pasa el límite de un presupuesto quincenal o semanal a su equivalente mensual."""
    p = plan.normalizar_periodo(periodo)
    if p == "biweekly":
        return limite * 2
    if p == "weekly":
        return limite * plan.DIAS_MES_PROMEDIO / 7
    return limite


def presupuesto_vs_real(movs: list[dict], presupuestos: list[dict], rango: dict, hoy: datetime) -> dict:
    """Para cada categoría con presupuesto activo: lo presupuestado para el rango (el límite mensual repartido por
    días: un mes completo = 1 límite, tres meses = 3, medio mes = medio), lo gastado de verdad, lo que queda y el %.
    Los sobres movidos a mano (`sobre_ajuste`) solo cuentan si el rango incluye el mes en curso, que es donde viven."""
    gastos = inf._gastos_por_categoria(movs, rango)
    incluye_mes_actual = rango["desde"] <= inf.inicio_mes(hoy.year, hoy.month) < rango["hasta"]
    fraccion = _fraccion_de_meses(rango)
    # Puede haber más de un presupuesto activo en la misma categoría (la base no lo impide): se suman sus límites y el
    # gasto de esa categoría se cuenta UNA sola vez (si no, el total gastado saldría inflado).
    por_cat: dict[str, dict] = {}
    for p in presupuestos:
        if not p.get("activo", True):
            continue
        f = por_cat.setdefault(p["categoria"], {"presup": 0.0, "alerta": p.get("alerta_pct") or 80})
        f["presup"] += _limite_mensual(p["limite"], p.get("periodo")) * fraccion
        if incluye_mes_actual:
            f["presup"] += p.get("sobre_ajuste") or 0
        f["alerta"] = min(f["alerta"], p.get("alerta_pct") or 80)
    filas = []
    for categoria, f in por_cat.items():
        presup, alerta = f["presup"], f["alerta"]
        gastado = gastos.get(categoria, {"monto": 0.0})["monto"]
        pct = round(gastado / presup * 100, 1) if presup > 0 else None
        if pct is None:
            estado = "sin_limite"
        elif pct >= 100:
            estado = "excedido"
        elif pct >= alerta:
            estado = "cerca"
        else:
            estado = "dentro"
        filas.append({"categoria": categoria, "presupuesto": round(presup), "gastado": round(gastado),
                      "disponible": round(presup - gastado), "pct": pct, "estado": estado, "alerta_pct": alerta})
    filas.sort(key=lambda f: (f["pct"] is None, -(f["pct"] or 0)))
    presup_total = sum(f["presupuesto"] for f in filas)
    gastado_total = sum(f["gastado"] for f in filas)
    con_presupuesto = {f["categoria"] for f in filas}
    fuera = sum(v["monto"] for c, v in gastos.items() if c not in con_presupuesto)
    return {
        "categorias": filas,
        "presupuesto_total": presup_total,
        "gastado_total": gastado_total,
        "disponible_total": presup_total - gastado_total,
        "pct_total": round(gastado_total / presup_total * 100, 1) if presup_total > 0 else None,
        "gasto_sin_presupuesto": round(fuera),
        "hay_presupuestos": bool(filas),
        "meses_equivalentes": round(fraccion, 2),
    }


# ── Hallazgos (solo reglas sobre cifras reales) ─────────────────────────────────────────────
def _cop(v: float) -> str:
    return "$" + f"{abs(round(v)):,}".replace(",", ".")


def en_periodo(etiqueta: str) -> str:
    """«en octubre de 2026», «durante los últimos 3 meses», «en el periodo del 1 de junio al 25 de noviembre»:
    las etiquetas de rango ya traen su artículo y «en del …» no se lee."""
    if etiqueta.startswith("del "):
        return f"en el periodo {etiqueta}"
    if etiqueta.startswith(("los ", "el ", "la ")):
        return f"durante {etiqueta}"
    return f"en {etiqueta}"


def _pct_txt(v: float) -> str:
    return f"{abs(v):.1f}".replace(".", ",").removesuffix(",0") + " %"


def hallazgos(totales: dict, informe: dict, presupuesto: dict, etiqueta: str, max_n: int = 5) -> list[dict]:
    """Lo que se puede afirmar con los números del periodo. Cada hallazgo lleva sus cifras (`datos`) para poder
    verificarlo, el periodo y a dónde ir a verlo. Si no hay base para afirmar algo, simplemente no aparece."""
    out: list[dict] = []
    ing, gas, bal = totales["ingresos"], totales["gastos"], totales["balance"]
    if ing == 0 and gas == 0:
        return out

    if ing == 0 and gas > 0:
        out.append({
            "id": "sin_ingresos", "tono": "atento", "prioridad": 2,
            "titulo": "No registraste ingresos en este periodo",
            "texto": (f"Salió {_cop(gas)} {en_periodo(etiqueta)} y no hay ingresos anotados, así que el flujo neto es "
                      f"−{_cop(gas)}. Si te entró plata, anótala para que el resumen sea fiel."),
            "datos": {"ingresos": 0, "gastos": gas, "neto": bal}, "enlace": "/agregar?tipo=ingreso",
        })
    elif bal != 0:
        positivo = bal > 0
        out.append({
            "id": "flujo", "tono": "bueno" if positivo else "atento", "prioridad": 2,
            "titulo": "Tu flujo neto es positivo" if positivo else "Tu flujo neto es negativo",
            "texto": (f"Entró {_cop(ing)} y salió {_cop(gas)} {en_periodo(etiqueta)}: te {'sobraron' if positivo else 'faltaron'} "
                      f"{_cop(bal)}."),
            "datos": {"ingresos": ing, "gastos": gas, "neto": bal}, "enlace": "/informes?tab=resumen",
        })

    var = totales.get("variacion") or {}
    pt = var.get("tasa_ahorro_puntos")
    if pt is not None and abs(pt) >= 1:
        mejora = pt > 0
        out.append({
            "id": "tasa", "tono": "bueno" if mejora else "atento", "prioridad": 1,
            "titulo": "Tu tasa de ahorro mejoró" if mejora else "Tu tasa de ahorro bajó",
            "texto": (f"Pasó de {_pct_txt(totales['anterior']['tasa_ahorro'])} a {_pct_txt(totales['tasa_ahorro'])} "
                      f"frente a {totales['anterior']['etiqueta']}."),
            "datos": {"tasa_ahorro": totales["tasa_ahorro"], "tasa_anterior": totales["anterior"]["tasa_ahorro"], "puntos": pt},
            "enlace": "/informes?tab=resumen",
        })

    gpct = var.get("gastos_pct")
    if gpct is not None and abs(gpct) >= UMBRAL_CAMBIO_PCT and totales["anterior"]["gastos"] > 0:
        sube = gpct > 0
        out.append({
            "id": "gastos", "tono": "atento" if sube else "bueno", "prioridad": 3,
            "titulo": "Gastaste más que el periodo anterior" if sube else "Gastaste menos que el periodo anterior",
            "texto": (f"{_cop(gas)} contra {_cop(totales['anterior']['gastos'])} en {totales['anterior']['etiqueta']} "
                      f"({'+' if sube else '−'}{_pct_txt(gpct)})."),
            "datos": {"gastos": gas, "anterior": totales["anterior"]["gastos"], "variacion_pct": gpct},
            "enlace": "/informes?tab=gastos",
        })

    cats = informe.get("categorias") or []
    if cats and informe.get("total"):
        top = cats[0]
        if top["pct"] >= UMBRAL_PESO_CATEGORIA:
            out.append({
                "id": "peso_categoria", "tono": "neutro", "prioridad": 4,
                "titulo": f"{top['categoria']} es tu mayor gasto",
                "texto": f"Representa el {_pct_txt(top['pct'])} de tus gastos ({_cop(top['monto'])}).",
                "datos": {"categoria": top["categoria"], "monto": top["monto"], "pct": top["pct"]},
                "enlace": "/informes?tab=gastos",
            })
        # La categoría que más subió en pesos (con base previa y un cambio que se note frente al gasto total).
        subidas = [c for c in cats if c["variacion_pct"] is not None and c["variacion_pct"] >= 20
                   and c["diferencia"] >= max(0.05 * informe["total"], 20_000)]
        if subidas:
            c = max(subidas, key=lambda x: x["diferencia"])
            out.append({
                "id": "sube_categoria", "tono": "atento", "prioridad": 2,
                "titulo": f"Tu gasto en {c['categoria']} aumentó",
                "texto": (f"{_cop(c['monto'])} contra {_cop(c['anterior'])} antes ({'+' if c['diferencia'] > 0 else '−'}"
                          f"{_pct_txt(c['variacion_pct'])})."),
                "datos": {"categoria": c["categoria"], "monto": c["monto"], "anterior": c["anterior"], "variacion_pct": c["variacion_pct"]},
                "enlace": "/informes?tab=gastos",
            })

    if presupuesto.get("hay_presupuestos"):
        pasados = [c for c in presupuesto["categorias"] if c["estado"] == "excedido"]
        cerca = [c for c in presupuesto["categorias"] if c["estado"] == "cerca"]
        if pasados:
            nombres = ", ".join(c["categoria"] for c in pasados[:3])
            out.append({
                "id": "presupuesto_excedido", "tono": "atento", "prioridad": 1,
                "titulo": f"{len(pasados)} {'presupuesto superado' if len(pasados) == 1 else 'presupuestos superados'}",
                "texto": f"Te pasaste en {nombres}.", "datos": {"categorias": [c["categoria"] for c in pasados]},
                "enlace": "/presupuesto",
            })
        elif cerca:
            nombres = ", ".join(c["categoria"] for c in cerca[:3])
            out.append({
                "id": "presupuesto_cerca", "tono": "atento", "prioridad": 2,
                "titulo": "Estás cerca de superar un presupuesto",
                "texto": f"Ya usaste la mayor parte de {nombres}.", "datos": {"categorias": [c["categoria"] for c in cerca]},
                "enlace": "/presupuesto",
            })

    out.sort(key=lambda h: h["prioridad"])
    return out[:max_n]


# ── Tasa de ahorro mes a mes ────────────────────────────────────────────────────────────────
def resumen_tasa(meses: list[dict]) -> dict:
    """Promedio ponderado (flujo neto total / ingresos totales de los meses CON ingresos: un mes de ingresos grandes
    pesa más que uno pequeño, que es lo que de verdad se ahorró), mejor y peor mes. Los meses sin ingresos no tienen
    tasa (None) y no entran: no se inventa un 0 %."""
    con = [m for m in meses if m.get("tasa_ahorro") is not None]
    if not con:
        return {"promedio": None, "mejor": None, "peor": None, "meses_con_tasa": 0}
    ing = sum(m["ingresos"] for m in con)
    bal = sum(m["balance"] for m in con)
    mejor = max(con, key=lambda m: m["tasa_ahorro"])
    peor = min(con, key=lambda m: m["tasa_ahorro"])
    return {"promedio": round(bal / ing * 100, 1) if ing > 0 else None,
            "mejor": {"mes": mejor["mes"], "etiqueta_larga": mejor["etiqueta_larga"], "tasa_ahorro": mejor["tasa_ahorro"]},
            "peor": {"mes": peor["mes"], "etiqueta_larga": peor["etiqueta_larga"], "tasa_ahorro": peor["tasa_ahorro"]},
            "meses_con_tasa": len(con)}
