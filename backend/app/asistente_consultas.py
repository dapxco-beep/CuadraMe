"""
Preguntas típicas del asistente resueltas con CÁLCULO DETERMINISTA (sin IA):
en qué gasté más, cuánto gasté en X, comparación entre periodos y "voy bien
con el presupuesto".

Reglas:
- Todo sale de `d["movs"]` (movimientos con la regla contable ya aplicada: sin
  pagos de tarjeta ni traslados, en COP) y de funciones puras de informe.py.
- Toda respuesta dice el PERIODO explícito ("En julio de 2026 gastaste...").
- Si el periodo no tiene datos, lo dice y ofrece el último mes que sí los tiene.
- Si no entiende, sugiere preguntas útiles.
"""
import re
from datetime import datetime, timedelta

from app import informe as inf
from app.asistente import MESES, _norm, cop

SUGERENCIAS_UTILES = [
    "¿En qué gasté más este mes?",
    "¿Cuánto gasté en comida el mes pasado?",
    "¿Gasté más o menos que el mes pasado?",
    "¿Voy bien con mi presupuesto?",
    "¿Tengo algún gasto fuera de lo normal?",
]

_NUM_MES = {n: i + 1 for i, n in enumerate(MESES)}
_NUM_MES["setiembre"] = 9
_RE_MES = re.compile(r"\b(" + "|".join(_NUM_MES) + r")\b(?:\s+(?:de\s+|del\s+)?(20\d\d))?")

_RE_COMPARAR = re.compile(
    r"compar|frente al mes|respecto (?:al|a) mes|versus|\bvs\b|que el mes (?:pasado|anterior)|"
    r"que el (?:pasado|anterior)|mes a mes|gaste (?:mas|menos) que"
)
_RE_PRESUPUESTO = re.compile(r"\bpresupuestos?\b")
_RE_CREAR = re.compile(r"\b(?:crear|crea|nuevo|agregar|anadir|configurar|eliminar|borrar)\b")
_RE_GASTO_EN = re.compile(
    r"\bcuanto (?:he |lleve |llevo |se me fue |me gaste |gastamos )?(?:gaste|gastado|gasto|pague|pagado|gastando)\b(?:\s+(?:en|de|por|con)\s+(.+))?"
)
_RE_GASTADO_EN = re.compile(r"\bcuanto (?:llevo|lleve) gastad[oa]\b(?:\s+(?:en|de|por|con)\s+(.+))?")

_RE_PERIODO_TEXTO = re.compile(
    r"\b(?:este|ese|el|en el|del)\s+mes\b|\bmes\s+(?:pasado|anterior|actual)\b|\bultimo\s+mes\b|"
    r"\b(?:este|en el|del|el)\s+ano\b|\besta\s+semana\b|\bsemana\s+pasada\b|"
    r"\bultimos?\s+(?:\d+|tres|seis|doce)\s+(?:dias|meses)\b|\btrimestre\b|\bhoy\b|\bayer\b|"
    + _RE_MES.pattern + r"|\b20\d\d\b"
)
_STOP = {"el", "la", "los", "las", "un", "una", "mi", "mis", "en", "de", "del", "por", "con", "este", "esta",
         "durante", "total", "todo", "todos", "gastos", "gasto", "plata", "dinero", "pesos", "pasado", "anterior", "ultimo", "y", "a", "al", "mes"}
_GENERICOS = {"", "total", "todo", "general", "plata", "dinero"}


# ── periodos ───────────────────────────────────────────────────────

def _rango_dias(hoy: datetime, desde: datetime, hasta_incl: datetime, etiqueta: str) -> dict:
    r = inf.rango_periodo("rango", hoy, desde.date().isoformat(), hasta_incl.date().isoformat())
    r["etiqueta"] = etiqueta
    return r


_NUM_PALABRA = {"tres": 3, "seis": 6, "doce": 12}


def parsear_periodo(t: str, hoy: datetime) -> dict | None:
    """Periodo mencionado en un texto YA normalizado (sin tildes, minúsculas), o
    None si no menciona ninguno. Devuelve un rango de informe.py."""
    m = re.search(r"\bultimos?\s+(\d+|tres|seis|doce)\s+(dias|meses)\b", t)
    if m:
        n = _NUM_PALABRA.get(m.group(1)) or int(m.group(1))
        if m.group(2) == "dias" and 1 <= n <= 366:
            ini = (hoy - timedelta(days=n - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
            return _rango_dias(hoy, ini, hoy, f"los últimos {n} días")
        if m.group(2) == "meses" and 1 <= n <= 24:
            a, mes = inf.sumar_meses(hoy.year, hoy.month, -(n - 1))
            return _rango_dias(hoy, inf.inicio_mes(a, mes), hoy, f"los últimos {n} meses" if n > 1 else "este mes")
    if re.search(r"\btrimestre\b", t):
        return inf.rango_periodo("3_meses", hoy)
    if re.search(r"\bmes (?:pasado|anterior)\b|\bultimo mes\b", t):
        return inf.rango_periodo("mes_pasado", hoy)
    if re.search(r"\b(?:este|en el|del|el) ano\b", t):
        return inf.rango_periodo("anio", hoy)
    if re.search(r"\bsemana pasada\b", t):
        lunes = (hoy - timedelta(days=hoy.weekday() + 7)).replace(hour=0, minute=0, second=0, microsecond=0)
        return _rango_dias(hoy, lunes, lunes + timedelta(days=6), "la semana pasada")
    if re.search(r"\besta semana\b", t):
        return inf.rango_periodo("semana", hoy)
    mm = _RE_MES.search(t)
    if mm:
        num = _NUM_MES[mm.group(1)]
        anio = int(mm.group(2)) if mm.group(2) else (hoy.year if num <= hoy.month else hoy.year - 1)
        return inf.rango_periodo("mes", hoy, mes=f"{anio}-{num:02d}")
    if re.search(r"\b(?:este|en el|del|el|mes) (?:mes|actual)\b|\bmes actual\b", t):
        return inf.rango_periodo("este_mes", hoy)
    return None


def _objeto(t_resto: str | None) -> str:
    """Lo que viene tras 'cuánto gasté en ...' sin la parte del periodo ni relleno."""
    if not t_resto:
        return ""
    t = _RE_PERIODO_TEXTO.sub(" ", t_resto)
    t = re.sub(r"[?¿!.,;:]", " ", t)
    palabras = [p for p in t.split() if p not in _STOP]
    return " ".join(palabras).strip()


def detectar_consulta(texto: str, hoy: datetime) -> dict | None:
    """Detecta las preguntas que resuelve este módulo. None si no es una de ellas."""
    t = _norm(texto)

    if _RE_COMPARAR.search(t):
        # "¿gasté más que el mes pasado?" compara ESTE mes contra el pasado: el
        # "mes pasado" que sigue a un conector de comparación es el término de
        # comparación, no el periodo preguntado.
        sin_termino = re.sub(r"\b(?:que|frente a|respecto a|vs|versus|con|contra|y)l?(?: el)? (?:mes )?(?:pasado|anterior)\b", " ", t)
        return {"intencion": "consulta", "tipo": "comparar", "periodo": parsear_periodo(sin_termino, hoy)}
    periodo = parsear_periodo(t, hoy)
    if _RE_PRESUPUESTO.search(t) and not _RE_CREAR.search(t):
        return {"intencion": "consulta", "tipo": "presupuesto", "periodo": None}
    m = _RE_GASTADO_EN.search(t) or _RE_GASTO_EN.search(t)
    if m:
        return {"intencion": "consulta", "tipo": "gasto_en", "periodo": periodo, "objeto": _objeto(m.group(1))}
    return None


# ── respuestas ─────────────────────────────────────────────────────

def _etiqueta(rango: dict, hoy: datetime) -> str:
    """'octubre de 2026' / 'octubre de 2026 (hasta hoy)' si el periodo llega a hoy."""
    parcial = rango["periodo"] in ("este_mes", "mes") and rango["hasta"] > hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    return rango["etiqueta"] + (" (hasta hoy)" if parcial and rango["periodo"] in ("este_mes", "mes") else "")


def _fuentes(d: dict, rango: dict) -> list[str]:
    n = sum(1 for m in d["movs"] if inf.en_rango(m, rango))
    return [f"Tus movimientos de {rango['etiqueta']} ({n})"]


def _p(x: float) -> str:
    """75.0 -> "75"; 87.5 -> "87,5"."""
    return str(int(x)) if float(x).is_integer() else str(x).replace(".", ",")


def _n(valor) -> str:
    return cop(valor)


def _con_signo(pct: float) -> str:
    return f"{'+' if pct > 0 else ''}{_p(pct)} %"


def _tramo(ant: dict) -> str:
    """' (los mismos días)' cuando se compara con un tramo parcial de un mes."""
    d = ant["desde"]
    return " (los mismos días)" if (ant["hasta"] - ant["desde"]).days < inf.dias_del_mes(d.year, d.month) else ""


def sin_datos(d: dict, rango: dict) -> dict:
    """El periodo no tiene gastos: se dice y se ofrece el último mes con datos."""
    hoy = d["hoy"]
    base = f"No tengo gastos registrados en {rango['etiqueta']}."
    ult = inf.ultimo_mes_con_datos(d["movs"])
    if not ult:
        return {"texto": base + " Registra el primero con algo como «Gasté 18.000 en almuerzo».",
                "fuentes": _fuentes(d, rango), "calculo": {}, "sin_datos": True}
    r = inf.rango_periodo("mes", hoy, mes=ult)
    resumen = inf.informe_gasto(d["movs"], r)
    top = ", ".join(f"{c['categoria']} {_n(c['monto'])}" for c in resumen["categorias"][:3])
    texto = (f"{base} Tu último mes con gastos es {r['etiqueta']}: gastaste {_n(resumen['total'])}"
             f" (lo que más pesó: {top}). Pregúntame «¿en qué gasté más en {r['etiqueta'].split(' de ')[0]}?» para el detalle.")
    return {"texto": texto, "fuentes": _fuentes(d, r), "sin_datos": True, "ultimo_mes": ult,
            "calculo": {"total": resumen["total"], "categorias": resumen["categorias"][:3]}}


def gasto_top(d: dict, rango: dict) -> dict:
    inf_g = inf.informe_gasto(d["movs"], rango)
    if not inf_g["hay_datos"]:
        return sin_datos(d, rango)
    hoy = d["hoy"]
    ant = inf.periodo_anterior(rango)
    top = ", ".join(f"{c['categoria']} {_n(c['monto'])} ({_p(c['pct'])} %)" for c in inf_g["categorias"][:3])
    texto = f"En {_etiqueta(rango, hoy)} gastaste {_n(inf_g['total'])}. Lo que más pesó: {top}."
    if inf_g["variacion_pct"] is not None:
        texto += (f" Es {_con_signo(inf_g['variacion_pct'])} frente a {ant['etiqueta']}{_tramo(ant)}, "
                  f"cuando gastaste {_n(inf_g['total_anterior'])}.")
    return {"texto": texto, "fuentes": _fuentes(d, rango),
            "calculo": {"total": inf_g["total"], "categorias": inf_g["categorias"][:5], "total_anterior": inf_g["total_anterior"],
                        "periodo": rango["etiqueta"]}}


def ahorro(d: dict, rango: dict) -> dict:
    res = inf.resumen_rango(d["movs"], rango)
    if not res["ingresos"] and not res["gastos"]:
        return sin_datos(d, rango)
    neto = res["ahorro"]
    signo = "ahorrado" if neto >= 0 else "gastado de más"
    texto = (f"En {_etiqueta(rango, d['hoy'])} entraron {_n(res['ingresos'])} y salieron {_n(res['gastos'])}: "
             f"has {signo} {_n(abs(neto))}.")
    return {"texto": texto, "fuentes": _fuentes(d, rango),
            "calculo": {"ingresos": round(res["ingresos"]), "gastos": round(res["gastos"]), "ahorro": round(neto)}}


_GENERICA = re.compile(r"[^a-z0-9 ]")


def _raiz(s: str) -> str:
    s = _GENERICA.sub("", _norm(s))
    for suf in ("es", "s"):
        if len(s) > 4 and s.endswith(suf):
            return s[: -len(suf)]
    return s


def _coincide(objeto: str, nombre: str) -> bool:
    a, b = _raiz(objeto), _raiz(nombre)
    return len(a) >= 3 and (a in b or (len(b) >= 3 and b in a))


def gasto_en(d: dict, rango: dict, objeto: str) -> dict:
    """Cuánto se gastó en una categoría o comercio (o en total si no se nombra)."""
    hoy = d["hoy"]
    objeto = (objeto or "").strip()
    if _norm(objeto) in _GENERICOS:
        return gasto_top(d, rango)

    gastos = [m for m in d["movs"] if m["tipo"] == "expense"]
    categorias = sorted({m["categoria"] for m in gastos})
    cats = [c for c in categorias if _coincide(objeto, c)]
    if cats:
        sel = lambda m: m["categoria"] in cats  # noqa: E731
        nombre = " / ".join(cats)
    else:
        clave = _norm(objeto)
        sel = lambda m: clave in _norm(m["descripcion"])  # noqa: E731
        nombre = objeto
        if not any(sel(m) for m in gastos):
            ejemplos = ", ".join(categorias[:6])
            extra = f" Tus categorías con gastos: {ejemplos}." if ejemplos else ""
            return {"texto": f"No encontré gastos de «{objeto}» en tus movimientos.{extra}",
                    "fuentes": _fuentes(d, rango), "calculo": {}, "no_entendido": True}

    en_p = [m for m in gastos if sel(m) and inf.en_rango(m, rango)]
    total = sum(m["monto"] for m in en_p)
    if not en_p:
        previos = [m for m in gastos if sel(m)]
        ult = max(inf.clave_mes(m["fecha"]) for m in previos)
        tot_ult = sum(m["monto"] for m in previos if inf.clave_mes(m["fecha"]) == ult)
        return {"texto": f"En {rango['etiqueta']} no gastaste nada en {nombre}. Lo último que registraste fue en "
                         f"{inf.nombre_mes(ult)}: {_n(tot_ult)}.",
                "fuentes": _fuentes(d, rango), "calculo": {"total": 0, "ultimo_mes": round(tot_ult)}}

    total_periodo = sum(m["monto"] for m in gastos if inf.en_rango(m, rango))
    ant = inf.periodo_anterior(rango)
    previo = sum(m["monto"] for m in gastos if sel(m) and inf.en_rango(m, ant))
    pct = round(total / total_periodo * 100, 1) if total_periodo else 0
    texto = (f"En {_etiqueta(rango, hoy)} gastaste {_n(total)} en {nombre} "
             f"({_p(pct)} % de tus gastos, en {len(en_p)} {'movimiento' if len(en_p) == 1 else 'movimientos'}).")
    calc = {"total": round(total), "pct": pct, "movimientos": len(en_p), "periodo": rango["etiqueta"]}
    if previo > 0:
        var = round((total - previo) / previo * 100, 1)
        texto += f" Frente a {ant['etiqueta']}{_tramo(ant)} ({_n(previo)}) es {_con_signo(var)}."
        calc.update({"anterior": round(previo), "variacion_pct": var})
    return {"texto": texto, "fuentes": _fuentes(d, rango), "calculo": calc}


def comparar(d: dict, rango: dict) -> dict:
    """Gasto/ingreso/ahorro del periodo contra el periodo anterior."""
    hoy = d["hoy"]
    ant = inf.periodo_anterior(rango)
    a = inf.resumen_rango(d["movs"], rango)
    b = inf.resumen_rango(d["movs"], ant)
    if not a["gastos"] and not b["gastos"]:
        return sin_datos(d, rango)
    if not a["gastos"]:
        return {"texto": f"En {rango['etiqueta']} no hay gastos para comparar. En {ant['etiqueta']} gastaste {_n(b['gastos'])}.",
                "fuentes": _fuentes(d, ant), "calculo": {"gastos_anterior": round(b["gastos"])}}
    if not b["gastos"]:
        return {"texto": f"En {_etiqueta(rango, hoy)} gastaste {_n(a['gastos'])}, pero no tengo gastos en {ant['etiqueta']} para comparar.",
                "fuentes": _fuentes(d, rango), "calculo": {"gastos": round(a['gastos'])}}

    var = round((a["gastos"] - b["gastos"]) / b["gastos"] * 100, 1)
    dif = a["gastos"] - b["gastos"]
    verbo = "más" if dif > 0 else "menos"
    texto = (f"En {_etiqueta(rango, hoy)} gastaste {_n(a['gastos'])}; en {ant['etiqueta']}{_tramo(ant)} gastaste {_n(b['gastos'])}. "
             + ("Gastaste igual." if round(dif) == 0 else f"Es {_n(abs(dif))} {verbo} ({_con_signo(var)}).") )
    ca = inf._gastos_por_categoria(d["movs"], rango)
    cb = inf._gastos_por_categoria(d["movs"], ant)
    cambios = {c: ca.get(c, {"monto": 0})["monto"] - cb.get(c, {"monto": 0})["monto"] for c in set(ca) | set(cb)}
    sube = max(cambios.items(), key=lambda kv: kv[1], default=None)
    baja = min(cambios.items(), key=lambda kv: kv[1], default=None)
    calc = {"gastos": round(a["gastos"]), "gastos_anterior": round(b["gastos"]), "diferencia": round(dif), "variacion_pct": var,
            "ingresos": round(a["ingresos"]), "ingresos_anterior": round(b["ingresos"])}
    if sube and sube[1] > 0:
        texto += f" Lo que más subió: {sube[0]} (+{_n(sube[1])})."
        calc["mayor_aumento"] = {"categoria": sube[0], "monto": round(sube[1])}
    if baja and baja[1] < 0:
        texto += f" Lo que más bajó: {baja[0]} (-{_n(-baja[1])})."
        calc["mayor_baja"] = {"categoria": baja[0], "monto": round(-baja[1])}
    if a["ingresos"] or b["ingresos"]:
        texto += f" Ingresos: {_n(a['ingresos'])} frente a {_n(b['ingresos'])}."
    return {"texto": texto, "fuentes": _fuentes(d, rango) + _fuentes(d, ant), "calculo": calc}


def presupuesto(d: dict) -> dict:
    """¿Voy bien con mis presupuestos? Gasto del mes por categoría frente al
    límite, y qué tanto del mes va transcurrido."""
    hoy = d["hoy"]
    rango = inf.rango_periodo("este_mes", hoy)
    pres = d.get("presupuestos") or []
    if not pres:
        return {"texto": "Aún no tienes presupuestos activos. Crea uno en Presupuesto y te digo cómo vas.",
                "fuentes": [], "calculo": {}}
    gastado = {c: v["monto"] for c, v in inf._gastos_por_categoria(d["movs"], rango).items()}
    mes_pct = round(hoy.day / inf.dias_del_mes(hoy.year, hoy.month) * 100)
    filas = []
    for p in pres:
        g = gastado.get(p["categoria"], 0.0)
        pct = round(g / p["limite"] * 100) if p["limite"] > 0 else 0
        filas.append({"categoria": p["categoria"], "gastado": round(g), "limite": round(p["limite"]), "pct": pct})
    filas.sort(key=lambda f: f["pct"], reverse=True)
    pasados = [f for f in filas if f["pct"] > 100]
    justos = [f for f in filas if 100 >= f["pct"] > mes_pct + 15]
    cab = f"En {rango['etiqueta']} (va el {mes_pct} % del mes)"
    if pasados:
        txt = "; ".join(f"{f['categoria']} {_n(f['gastado'])} de {_n(f['limite'])} ({f['pct']} %)" for f in pasados[:3])
        texto = f"{cab} ya te pasaste en: {txt}."
    elif justos:
        txt = "; ".join(f"{f['categoria']} {_n(f['gastado'])} de {_n(f['limite'])} ({f['pct']} %)" for f in justos[:3])
        texto = f"{cab} vas bien, pero ojo: gastas más rápido de lo que avanza el mes en {txt}."
    else:
        f = filas[0]
        texto = (f"{cab} vas bien: ninguna categoría pasa su límite. La más cargada es {f['categoria']} con "
                 f"{_n(f['gastado'])} de {_n(f['limite'])} ({f['pct']} %).")
    return {"texto": texto, "fuentes": _fuentes(d, rango) + [f"Tus presupuestos ({len(pres)})"],
            "calculo": {"mes_transcurrido_pct": mes_pct, "presupuestos": filas[:6]}}


def responder_consulta(intento: dict, d: dict) -> dict:
    """Despacha una consulta detectada. `intento['periodo']` None = este mes."""
    hoy = d["hoy"]
    rango = intento.get("periodo") or inf.rango_periodo("este_mes", hoy)
    tipo = intento["tipo"]
    if tipo == "comparar":
        return comparar(d, rango)
    if tipo == "presupuesto":
        return presupuesto(d)
    if tipo == "gasto_en":
        return gasto_en(d, rango, intento.get("objeto", ""))
    if tipo == "ahorro":
        return ahorro(d, rango)
    return gasto_top(d, rango)


def texto_no_entendi() -> str:
    return "No entendí esa pregunta. Puedo ayudarte con cosas como: " + " · ".join(SUGERENCIAS_UTILES[:4])
