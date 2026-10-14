"""
Informe de gasto: periodos, comparación y agregaciones. Funciones PURAS.

Reciben movimientos ya "efectivos": dicts {id, fecha, tipo, monto, categoria,
descripcion} donde `tipo` ya pasó por la regla contable (contabilidad.py:
'income' | 'expense' | 'transfer') y `monto` ya está en COP. Así el informe, el
asistente y los resúmenes cuentan exactamente igual (sin doble conteo de pagos
de tarjeta ni traslados).

Convención de rangos: [desde, hasta) -- `hasta` es EXCLUSIVO (00:00 del día
siguiente al último día incluido). Es lo que evita perder los movimientos del
último día cuando traen hora.
"""
import calendar
import re
import unicodedata
from datetime import datetime, timedelta

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
PERIODOS = ("este_mes", "mes_pasado", "3_meses", "anio", "semana", "rango", "mes")
MAX_DIAS_RANGO = 366 * 5


class PeriodoInvalido(ValueError):
    pass


def _dia(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def inicio_mes(anio: int, mes: int) -> datetime:
    return datetime(anio, mes, 1)


def sumar_meses(anio: int, mes: int, n: int) -> tuple[int, int]:
    total = anio * 12 + (mes - 1) + n
    return total // 12, total % 12 + 1


def clave_mes(dt: datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"


def nombre_mes(clave: str) -> str:
    """'2026-07' -> 'julio de 2026'."""
    a, m = (int(x) for x in clave.split("-"))
    return f"{MESES[m - 1]} de {a}"


def _fecha_corta(dt: datetime) -> str:
    return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}"


def _parsear_dia(texto: str) -> datetime:
    try:
        return _dia(datetime.fromisoformat(texto[:10]))
    except (ValueError, TypeError):
        raise PeriodoInvalido("Las fechas deben tener formato AAAA-MM-DD")


def _rango(desde: datetime, hasta: datetime, etiqueta: str, periodo: str) -> dict:
    return {"desde": desde, "hasta": hasta, "etiqueta": etiqueta, "periodo": periodo}


def rango_periodo(periodo: str, hoy: datetime, desde: str | None = None, hasta: str | None = None,
                  mes: str | None = None) -> dict:
    """{desde, hasta(exclusivo), etiqueta, periodo} para un periodo con nombre.

    este_mes   1 del mes actual -> hoy (inclusive)
    mes_pasado el mes calendario anterior completo
    3_meses    1 del mes de hace 2 meses -> hoy (3 meses de calendario)
    anio       1 de enero -> hoy
    semana     lunes de esta semana -> hoy
    mes        un mes concreto 'AAAA-MM' (completo; si es el actual, hasta hoy)
    rango      desde-hasta personalizado (ambos inclusive, 'AAAA-MM-DD')
    """
    manana = _dia(hoy) + timedelta(days=1)
    if periodo == "este_mes":
        ini = inicio_mes(hoy.year, hoy.month)
        return _rango(ini, manana, f"{MESES[hoy.month - 1]} de {hoy.year}", periodo)
    if periodo == "mes_pasado":
        a, m = sumar_meses(hoy.year, hoy.month, -1)
        return _rango(inicio_mes(a, m), inicio_mes(hoy.year, hoy.month), f"{MESES[m - 1]} de {a}", periodo)
    if periodo == "3_meses":
        a, m = sumar_meses(hoy.year, hoy.month, -2)
        return _rango(inicio_mes(a, m), manana, "los últimos 3 meses", periodo)
    if periodo == "anio":
        return _rango(datetime(hoy.year, 1, 1), manana, f"el año {hoy.year}", periodo)
    if periodo == "semana":
        lunes = _dia(hoy) - timedelta(days=hoy.weekday())
        return _rango(lunes, manana, "esta semana", periodo)
    if periodo == "mes":
        try:
            a, m = (int(x) for x in (mes or "").split("-"))
            if not 1 <= m <= 12 or not 1900 < a < 2200:
                raise ValueError
        except ValueError:
            raise PeriodoInvalido("El mes debe tener formato AAAA-MM")
        ini = inicio_mes(a, m)
        fin = inicio_mes(*sumar_meses(a, m, 1))
        if ini <= hoy < fin:
            fin = manana
        return _rango(ini, fin, f"{MESES[m - 1]} de {a}", periodo)
    if periodo == "rango":
        if not desde or not hasta:
            raise PeriodoInvalido("Indica las fechas desde y hasta")
        d, h = _parsear_dia(desde), _parsear_dia(hasta)
        if h < d:
            raise PeriodoInvalido("La fecha 'hasta' no puede ser anterior a 'desde'")
        if (h - d).days > MAX_DIAS_RANGO:
            raise PeriodoInvalido("El rango es demasiado largo (máximo 5 años)")
        etiqueta = f"del {_fecha_corta(d)} al {_fecha_corta(h)}" if d != h else f"el {_fecha_corta(d)}"
        return _rango(d, h + timedelta(days=1), etiqueta, periodo)
    raise PeriodoInvalido("Periodo no válido")


def periodo_anterior(rango: dict) -> dict:
    """El periodo con el que se compara. Si el rango es (parte de) UN mes
    calendario que arranca el día 1, se compara con el mismo tramo del mes
    anterior (el 12 de octubre se compara con el 1-12 de septiembre, no con
    septiembre completo, para no sugerir una caída falsa). Si no, con el rango
    de igual duración inmediatamente anterior."""
    d, h = rango["desde"], rango["hasta"]
    largo = h - d
    if d.day == 1 and h <= inicio_mes(*sumar_meses(d.year, d.month, 1)):
        a, m = sumar_meses(d.year, d.month, -1)
        ini = inicio_mes(a, m)
        fin_mes = inicio_mes(d.year, d.month)
        fin = min(ini + largo, fin_mes)
        return _rango(ini, fin, f"{MESES[m - 1]} de {a}", "anterior")
    ini = d - largo
    fin = d - timedelta(days=1)
    return _rango(ini, d, f"los {largo.days} días anteriores ({ini.day} {MESES[ini.month - 1][:3]} - "
                          f"{fin.day} {MESES[fin.month - 1][:3]})", "anterior")


def en_rango(m: dict, rango: dict) -> bool:
    return rango["desde"] <= m["fecha"] < rango["hasta"]


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t or "")
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip().lower()


def clave_comercio(descripcion: str) -> str:
    """'  Éxito  Calle 80 ' -> 'exito calle 80' (para agrupar el mismo comercio)."""
    return _norm(descripcion)


def _pct(v: float, total: float) -> float:
    return round(v / total * 100, 1) if total else 0.0


def _variacion(actual: float, previo: float):
    """% de cambio; None si no hay base de comparación (previo = 0)."""
    return round((actual - previo) / previo * 100, 1) if previo > 0 else None


def _gastos_por_categoria(movs: list[dict], rango: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in movs:
        if m["tipo"] == "expense" and en_rango(m, rango):
            f = out.setdefault(m.get("categoria") or "Otros", {"monto": 0.0, "num": 0})
            f["monto"] += m["monto"]
            f["num"] += 1
    return out


def informe_gasto(movs: list[dict], rango: dict, anterior: dict | None = None, max_comercios: int = 8) -> dict:
    """Informe 'en qué gasto mi plata' para un rango, con la comparación contra
    `anterior` (por defecto, el que dicta `periodo_anterior`)."""
    anterior = anterior or periodo_anterior(rango)
    actual = _gastos_por_categoria(movs, rango)
    previo = _gastos_por_categoria(movs, anterior)
    total = sum(f["monto"] for f in actual.values())
    total_prev = sum(f["monto"] for f in previo.values())
    ingresos = sum(m["monto"] for m in movs if m["tipo"] == "income" and en_rango(m, rango))

    categorias = []
    for cat, f in sorted(actual.items(), key=lambda kv: kv[1]["monto"], reverse=True):
        prev = previo.get(cat, {"monto": 0.0})["monto"]
        categorias.append({
            "categoria": cat,
            "monto": round(f["monto"]),
            "pct": _pct(f["monto"], total),
            "num": f["num"],
            "anterior": round(prev),
            "diferencia": round(f["monto"] - prev),
            "variacion_pct": _variacion(f["monto"], prev),
        })

    comercios: dict[str, dict] = {}
    for m in movs:
        if m["tipo"] == "expense" and en_rango(m, rango):
            k = clave_comercio(m.get("descripcion", ""))
            if not k:
                continue
            c = comercios.setdefault(k, {"nombre": (m.get("descripcion") or "").strip(), "monto": 0.0, "num": 0})
            c["monto"] += m["monto"]
            c["num"] += 1
    top = sorted(comercios.values(), key=lambda c: c["monto"], reverse=True)[:max_comercios]

    return {
        "desde": rango["desde"].date().isoformat(),
        "hasta": (rango["hasta"] - timedelta(days=1)).date().isoformat(),
        "etiqueta": rango["etiqueta"],
        "anterior": {
            "desde": anterior["desde"].date().isoformat(),
            "hasta": (anterior["hasta"] - timedelta(days=1)).date().isoformat(),
            "etiqueta": anterior["etiqueta"],
        },
        "total": round(total),
        "ingresos": round(ingresos),
        "ahorro": round(ingresos - total),
        "num_movimientos": sum(f["num"] for f in actual.values()),
        "total_anterior": round(total_prev),
        "diferencia": round(total - total_prev),
        "variacion_pct": _variacion(total, total_prev),
        "categorias": categorias,
        "comercios": [{"nombre": c["nombre"][:60], "monto": round(c["monto"]), "num": c["num"]} for c in top],
        "hay_datos": bool(actual),
    }


def meses_con_datos(movs: list[dict]) -> list[dict]:
    """Meses (de más viejo a más nuevo) que tienen ingresos o gastos efectivos."""
    por_mes: dict[str, dict] = {}
    for m in movs:
        if m["tipo"] not in ("income", "expense"):
            continue
        f = por_mes.setdefault(clave_mes(m["fecha"]), {"ingresos": 0.0, "gastos": 0.0, "num": 0})
        f["num"] += 1
        f["ingresos" if m["tipo"] == "income" else "gastos"] += m["monto"]
    return [
        {"mes": k, "etiqueta": nombre_mes(k), "ingresos": round(v["ingresos"]), "gastos": round(v["gastos"]),
         "ahorro": round(v["ingresos"] - v["gastos"]), "num": v["num"]}
        for k, v in sorted(por_mes.items())
    ]


def ultimo_mes_con_datos(movs: list[dict], antes_de: datetime | None = None, tipo: str = "expense") -> str | None:
    """Clave 'AAAA-MM' del mes más reciente con movimientos del `tipo` dado
    (opcionalmente anterior al mes de `antes_de`)."""
    limite = clave_mes(antes_de) if antes_de else None
    claves = {clave_mes(m["fecha"]) for m in movs if m["tipo"] == tipo and (limite is None or clave_mes(m["fecha"]) < limite)}
    return max(claves) if claves else None


def gasto_diario(movs: list[dict], rango: dict) -> list[dict]:
    """[{dia 'AAAA-MM-DD', gasto, ingreso}] para CADA día del rango (con ceros)."""
    gasto: dict[str, float] = {}
    ingreso: dict[str, float] = {}
    for m in movs:
        if en_rango(m, rango) and m["tipo"] in ("income", "expense"):
            k = m["fecha"].date().isoformat()
            destino = gasto if m["tipo"] == "expense" else ingreso
            destino[k] = destino.get(k, 0.0) + m["monto"]
    dias = []
    cursor = rango["desde"]
    while cursor < rango["hasta"]:
        k = cursor.date().isoformat()
        dias.append({"dia": k, "gasto": round(gasto.get(k, 0.0)), "ingreso": round(ingreso.get(k, 0.0))})
        cursor += timedelta(days=1)
    return dias


def resumen_rango(movs: list[dict], rango: dict) -> dict:
    """Ingresos, gastos, ahorro y top 3 categorías de un rango."""
    ing = sum(m["monto"] for m in movs if m["tipo"] == "income" and en_rango(m, rango))
    cats = _gastos_por_categoria(movs, rango)
    gas = sum(f["monto"] for f in cats.values())
    top = [{"categoria": c, "monto": v["monto"]} for c, v in sorted(cats.items(), key=lambda kv: kv[1]["monto"], reverse=True)[:3]]
    return {"ingresos": ing, "gastos": gas, "ahorro": ing - gas, "top_categorias": top}


def dias_del_mes(anio: int, mes: int) -> int:
    return calendar.monthrange(anio, mes)[1]


# ── Ingresos vs gastos ──────────────────────────────────────────────────────────────────────
def _totales(movs: list[dict], rango: dict) -> dict:
    """Ingresos, gastos, balance y tasa de ahorro de un rango. Solo movimientos con tipo efectivo
    'income' / 'expense' (los traslados, pagos de tarjeta y ajustes ya vienen como 'transfer')."""
    ing = gas = 0.0
    for m in movs:
        if en_rango(m, rango):
            if m["tipo"] == "income":
                ing += m["monto"]
            elif m["tipo"] == "expense":
                gas += m["monto"]
    bal = ing - gas
    return {"ingresos": round(ing), "gastos": round(gas), "balance": round(bal),
            "tasa_ahorro": round(bal / ing * 100, 1) if ing > 0 else None}


def _variacion_signo(actual: float, previo: float):
    """% de cambio contra el valor absoluto del previo (sirve para balances negativos); None sin base."""
    return round((actual - previo) / abs(previo) * 100, 1) if previo else None


def serie_mensual(movs: list[dict], hasta_mes: tuple[int, int], meses: int = 6) -> list[dict]:
    """Ingresos, gastos y balance de cada uno de los últimos `meses` meses (el último es `hasta_mes`)."""
    out = []
    for n in range(-(meses - 1), 1):
        a, m = sumar_meses(hasta_mes[0], hasta_mes[1], n)
        r = _rango(inicio_mes(a, m), inicio_mes(*sumar_meses(a, m, 1)), "", "mes")
        t = _totales(movs, r)
        out.append({"mes": f"{a}-{m:02d}", "etiqueta": f"{MESES[m - 1][:3]}", "etiqueta_larga": f"{MESES[m - 1]} de {a}",
                    "ingresos": t["ingresos"], "gastos": t["gastos"], "balance": t["balance"]})
    return out


def ingresos_gastos(movs: list[dict], rango: dict, anterior: dict | None = None, meses: int = 6) -> dict:
    """Comparación ingresos vs gastos de un rango, contra el periodo anterior y por mes."""
    anterior = anterior or periodo_anterior(rango)
    actual, previo = _totales(movs, rango), _totales(movs, anterior)
    ultimo = rango["hasta"] - timedelta(days=1)
    serie = serie_mensual(movs, (ultimo.year, ultimo.month), max(1, min(meses, 24)))
    return {
        "desde": rango["desde"].date().isoformat(),
        "hasta": (rango["hasta"] - timedelta(days=1)).date().isoformat(),
        "etiqueta": rango["etiqueta"],
        "anterior": {"desde": anterior["desde"].date().isoformat(),
                     "hasta": (anterior["hasta"] - timedelta(days=1)).date().isoformat(),
                     "etiqueta": anterior["etiqueta"], **previo},
        **actual,
        "variacion": {
            "ingresos_pct": _variacion(actual["ingresos"], previo["ingresos"]),
            "gastos_pct": _variacion(actual["gastos"], previo["gastos"]),
            "balance_pct": _variacion_signo(actual["balance"], previo["balance"]),
            "tasa_ahorro_puntos": (round(actual["tasa_ahorro"] - previo["tasa_ahorro"], 1)
                                   if actual["tasa_ahorro"] is not None and previo["tasa_ahorro"] is not None else None),
        },
        "meses": serie,
        "hay_datos": bool(actual["ingresos"] or actual["gastos"] or previo["ingresos"] or previo["gastos"]
                          or any(s["ingresos"] or s["gastos"] for s in serie)),
    }


MAX_MESES_EVOLUCION = 36
MAX_SEMANAS_EVOLUCION = 52
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _cubetas_evolucion(inicio: datetime, hoy: datetime, agrupar: str) -> list[tuple[datetime, datetime]]:
    """[(desde, hasta_exclusivo)] de cada mes (o semana lunes-domingo) desde `inicio` hasta el que contiene `hoy`."""
    out = []
    if agrupar == "semana":
        cur = _dia(inicio) - timedelta(days=_dia(inicio).weekday())
        while cur <= hoy:
            out.append((cur, cur + timedelta(days=7)))
            cur += timedelta(days=7)
    else:
        a, m = inicio.year, inicio.month
        while (a, m) <= (hoy.year, hoy.month):
            out.append((inicio_mes(a, m), inicio_mes(*sumar_meses(a, m, 1))))
            a, m = sumar_meses(a, m, 1)
    return out


def evolucion(movs: list[dict], hoy: datetime, agrupar: str = "mes", meses: int = 6,
              inicio_pp: datetime | None = None) -> dict:
    """Serie de tiempo de ingresos, gastos y ahorro (ingresos - gastos) por mes o por semana.

    Solo cuenta lo que ya clasificó la regla única (movs con tipo 'income' / 'expense'; los traslados, pagos de
    tarjeta y ajustes vienen como 'transfer' y no suman). `meses` = cuántos meses mirar atrás (0 = todo lo
    que hay, con tope). Nunca se dibuja antes del punto de partida (`inicio_pp`). Un periodo sin ningún
    movimiento va con `con_datos: false` y valores null (hueco, no un cero engañoso). `acumulado` es el ahorro
    sumado desde el primer periodo mostrado."""
    agrupar = "semana" if agrupar == "semana" else "mes"
    reales = [m for m in movs if m["tipo"] in ("income", "expense")]
    if meses and meses > 0:
        meses = min(meses, MAX_MESES_EVOLUCION)
        a, mm = sumar_meses(hoy.year, hoy.month, -(meses - 1))
        inicio = inicio_mes(a, mm)
    else:
        primero = min((m["fecha"] for m in reales), default=hoy)
        a, mm = sumar_meses(hoy.year, hoy.month, -(MAX_MESES_EVOLUCION - 1))
        inicio = max(_dia(primero).replace(day=1), inicio_mes(a, mm))
    if inicio_pp and inicio < inicio_pp:
        inicio = inicio_pp.replace(day=1) if agrupar == "mes" else inicio_pp
    cubetas = _cubetas_evolucion(inicio, hoy, agrupar)
    if agrupar == "semana" and len(cubetas) > MAX_SEMANAS_EVOLUCION:
        cubetas = cubetas[-MAX_SEMANAS_EVOLUCION:]
    puntos, acum = [], 0
    for d, h in cubetas:
        ing = gas = 0.0
        n = 0
        for m in reales:
            if d <= m["fecha"] < h:
                n += 1
                if m["tipo"] == "income":
                    ing += m["monto"]
                else:
                    gas += m["monto"]
        con = n > 0
        if con:
            acum += round(ing) - round(gas)
        ultimo = h - timedelta(days=1)
        if agrupar == "mes":
            etiqueta, larga = MESES_CORTOS[d.month - 1], f"{MESES[d.month - 1]} de {d.year}"
        else:
            etiqueta = f"{d.day} {MESES_CORTOS[d.month - 1]}"
            larga = f"semana del {d.day} de {MESES[d.month - 1]} al {ultimo.day} de {MESES[ultimo.month - 1]}"
        puntos.append({
            "clave": d.date().isoformat() if agrupar == "semana" else clave_mes(d),
            "etiqueta": etiqueta, "etiqueta_larga": larga,
            "desde": d.date().isoformat(), "hasta": ultimo.date().isoformat(),
            "ingresos": round(ing) if con else None, "gastos": round(gas) if con else None,
            "ahorro": round(ing) - round(gas) if con else None,
            "acumulado": acum, "con_datos": con,
            "en_curso": d <= hoy < h,
        })
    return {
        "agrupar": agrupar, "meses": meses, "puntos": puntos,
        "inicio": inicio_pp.date().isoformat() if inicio_pp else None,
        "meses_con_datos": len({m["fecha"].strftime("%Y-%m") for m in reales
                                if cubetas and cubetas[0][0] <= m["fecha"] < cubetas[-1][1]}),
        "hay_datos": any(p["con_datos"] for p in puntos),
    }


ETIQUETAS_RAZON = {
    "par": "Traslado entre tus cuentas", "par_comision": "Traslado entre tus cuentas",
    "decision": "Traslado entre tus cuentas", "regla": "Traslado entre tus cuentas",
    "traslado_app": "Traslado entre tus cuentas", "categoria": "Traslado entre tus cuentas",
    "posible": "Posible traslado", "pago_tarjeta": "Pago de tarjeta", "abono_tarjeta": "Pago de tarjeta",
    "ajuste": "Ajuste de saldo", "aporte_meta": "Aporte a meta",
}


def no_se_cuenta(movs: list[dict], rango: dict, limite: int = 300) -> dict:
    """Lo que NO entra en ingresos ni gastos del rango, para que la persona lo verifique."""
    filas = [m for m in movs if m["tipo"] == "transfer" and en_rango(m, rango)]
    filas.sort(key=lambda m: m["fecha"], reverse=True)
    grupos: dict[str, dict] = {}
    for m in filas:
        g = grupos.setdefault(ETIQUETAS_RAZON.get(m.get("razon"), "Otro"), {"cantidad": 0, "monto": 0.0})
        g["cantidad"] += 1
        g["monto"] += m["monto"]
    return {
        "etiqueta": rango["etiqueta"],
        "cantidad": len(filas),
        "grupos": [{"nombre": k, "cantidad": v["cantidad"], "monto": round(v["monto"])} for k, v in grupos.items()],
        "truncado": len(filas) > limite,
        "movimientos": [
            {"id": m["id"], "fecha": m["fecha"].isoformat(), "descripcion": m["descripcion"], "monto": round(m["monto"]),
             "cuenta_id": m.get("cuenta_id"), "motivo": ETIQUETAS_RAZON.get(m.get("razon"), "Otro"), "razon": m.get("razon"),
             "par": m.get("par")}
            for m in filas[:limite]
        ],
    }
