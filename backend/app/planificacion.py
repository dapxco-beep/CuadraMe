"""
Planificación financiera: funciones PURAS (sin base de datos ni red), para poder
probarlas con casos numéricos verificados a mano.

Cubre: periodos de presupuesto (mensual / quincenal / semanal), proyección de
cierre por categoría, reparto sugerido de un ingreso (regla 50/30/20 y sobres),
planificador de metas (con rendimiento EA opcional) y la descomposición del
crecimiento del patrimonio.

Convención de periodos: `fin` es EXCLUSIVO (primer día del periodo siguiente).
Los valores de `Presupuesto.periodo` ya existentes ("monthly") se respetan; los
nuevos son "biweekly" y "weekly".
"""
import calendar
import math
from datetime import date, datetime, timedelta
from typing import Optional

PERIODOS = ("monthly", "biweekly", "weekly")
_ALIAS_PERIODO = {
    "monthly": "monthly", "mensual": "monthly", "mes": "monthly",
    "biweekly": "biweekly", "quincenal": "biweekly", "quincena": "biweekly",
    "weekly": "weekly", "semanal": "weekly", "semana": "weekly",
}
DIAS_MES_PROMEDIO = 365.25 / 12  # 30,4375


def normalizar_periodo(periodo: Optional[str]) -> str:
    """Cualquier valor desconocido o vacío cae en 'monthly': así los datos
    antiguos nunca rompen los cálculos."""
    return _ALIAS_PERIODO.get((periodo or "").strip().lower(), "monthly")


def _a_fecha(d) -> date:
    return d.date() if isinstance(d, datetime) else d


def _dia_en_mes(anio: int, mes: int, dia: int) -> date:
    return date(anio, mes, min(dia, calendar.monthrange(anio, mes)[1]))


def _mes_siguiente(anio: int, mes: int) -> tuple:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def _mes_anterior(anio: int, mes: int) -> tuple:
    return (anio - 1, 12) if mes == 1 else (anio, mes - 1)


def _inicios_quincena(dia_pago: Optional[int]) -> tuple:
    """Días del mes en que arranca cada quincena. Sin día de pago: 1 y 16
    (1-15 / 16-fin). Con día de pago d, la quincena arranca el día d y 15
    días después: d=5 -> quincenas 5-19 y 20-4; d=30 -> se pliega a 15 y 30."""
    if not dia_pago:
        return 1, 16
    a = int(dia_pago)
    a = a - 15 if a > 15 else a
    a = max(1, a)
    return a, a + 15


def rango_periodo(hoy, periodo: str = "monthly", dia_pago: Optional[int] = None) -> dict:
    """Periodo que contiene a `hoy`. Devuelve inicio, fin (exclusivo) y los
    conteos de días. `dias_transcurridos` incluye el día de hoy; `dias_restantes`
    son los días COMPLETOS que faltan después de hoy."""
    h = _a_fecha(hoy)
    periodo = normalizar_periodo(periodo)
    if periodo == "weekly":
        inicio = h - timedelta(days=h.weekday())  # lunes
        fin = inicio + timedelta(days=7)
    elif periodo == "biweekly":
        a, b = _inicios_quincena(dia_pago)
        ini_a = _dia_en_mes(h.year, h.month, a)
        ini_b = _dia_en_mes(h.year, h.month, b)
        if h < ini_a:
            ay, am = _mes_anterior(h.year, h.month)
            inicio, fin = _dia_en_mes(ay, am, b), ini_a
        elif h < ini_b:
            inicio, fin = ini_a, ini_b
        else:
            ny, nm = _mes_siguiente(h.year, h.month)
            inicio, fin = ini_b, _dia_en_mes(ny, nm, a)
    else:
        inicio = date(h.year, h.month, 1)
        ny, nm = _mes_siguiente(h.year, h.month)
        fin = date(ny, nm, 1)
    total = (fin - inicio).days
    transcurridos = (h - inicio).days + 1
    return {
        "periodo": periodo,
        "inicio": inicio,
        "fin": fin,
        "dias_totales": total,
        "dias_transcurridos": transcurridos,
        "dias_restantes": total - transcurridos,
    }


def periodo_anterior(inicio, periodo: str, dia_pago: Optional[int] = None) -> dict:
    """El periodo inmediatamente anterior al que arranca en `inicio`."""
    return rango_periodo(_a_fecha(inicio) - timedelta(days=1), periodo, dia_pago)


def clave_periodo(inicio, periodo: str) -> str:
    """Marca para no repetir alertas dentro de un mismo periodo. Mensual conserva
    el formato histórico 'YYYY-MM' (así las alertas ya enviadas siguen valiendo)."""
    inicio = _a_fecha(inicio)
    if normalizar_periodo(periodo) == "monthly":
        return inicio.strftime("%Y-%m")
    return inicio.isoformat()


def formato_cop(v: float) -> str:
    """$1.234.567 (punto como separador de miles, como se escribe en Colombia)."""
    return "$" + f"{round(v):,}".replace(",", ".")


# ------------------------------------------------------------------ proyección

def proyectar_cierre(gastado: float, limite: float, rango: dict,
                     historico: Optional[list] = None, categoria: str = "") -> dict:
    """Proyección de cierre de UN presupuesto.

    ritmo actual = gastado / días transcurridos (hoy cuenta como día transcurrido).
    Con histórico (gastos totales de periodos anteriores, mismo largo de periodo),
    el ritmo se mezcla con el histórico diario: cuanto menos avanzado va el
    periodo, más pesa el histórico (peso del ritmo actual = transcurridos/totales).
    proyectado = gastado + ritmo_mezclado * días_restantes.
    """
    total = max(1, rango["dias_totales"])
    transc = max(1, rango["dias_transcurridos"])
    rest = max(0, rango["dias_restantes"])
    gastado = max(0.0, gastado or 0.0)
    limite = limite or 0.0

    ritmo_actual = gastado / transc
    hist = [h for h in (historico or []) if h and h > 0]
    promedio_anterior = (sum(hist) / len(hist)) if hist else None
    if promedio_anterior is not None:
        w = min(1.0, transc / total)
        ritmo = ritmo_actual * w + (promedio_anterior / total) * (1 - w)
    else:
        ritmo = ritmo_actual
    proyectado = gastado + ritmo * rest

    pct_usado = (gastado / limite * 100) if limite > 0 else 0.0
    pct_proyectado = (proyectado / limite * 100) if limite > 0 else 0.0

    if limite <= 0:
        estado = "sin_limite"
    elif gastado > limite:
        estado = "excedido"
    elif proyectado > limite:
        estado = "en_riesgo"
    elif proyectado >= limite * 0.9:
        estado = "atencion"
    else:
        estado = "bien"

    dias_hasta_limite = None
    if limite > 0 and ritmo > 0 and gastado <= limite:
        dias_hasta_limite = (limite - gastado) / ritmo

    vs_anterior_pct = None
    if promedio_anterior:
        vs_anterior_pct = round((proyectado - promedio_anterior) / promedio_anterior * 100, 1)

    res = {
        "categoria": categoria,
        "gastado": gastado,
        "limite": limite,
        "ritmo_diario": ritmo,
        "proyectado": proyectado,
        "pct_usado": round(pct_usado, 1),
        "pct_proyectado": round(pct_proyectado, 1),
        "dias_restantes": rest,
        "estado": estado,
        "dias_hasta_limite": dias_hasta_limite,
        "promedio_anterior": promedio_anterior,
        "vs_anterior_pct": vs_anterior_pct,
    }
    res["mensaje"] = mensaje_proyeccion(res)
    return res


def mensaje_proyeccion(p: dict) -> str:
    nombre = p.get("categoria") or "este presupuesto"
    pct = round(p["pct_usado"])
    rest = p["dias_restantes"]
    dias = f"{rest} día" + ("" if rest == 1 else "s")
    faltan = "falta" if rest == 1 else "faltan"
    if p["estado"] == "sin_limite":
        return f"Define un límite para {nombre} y te digo cómo vas a cerrar."
    if p["estado"] == "excedido":
        return f"Ya te pasaste en {nombre} por {formato_cop(p['gastado'] - p['limite'])}."
    if rest == 0:
        return f"Hoy cierra {nombre}: llevas {pct}% del límite."
    if p["estado"] == "en_riesgo":
        exceso = p["proyectado"] - p["limite"]
        return (f"Llevas {pct}% de {nombre} y {faltan} {dias}; a este ritmo cerrarías en "
                f"{formato_cop(p['proyectado'])}, {formato_cop(exceso)} por encima del límite.")
    if p["estado"] == "atencion":
        return (f"Llevas {pct}% de {nombre} y {faltan} {dias}; cerrarías en "
                f"{formato_cop(p['proyectado'])}, casi al tope de {formato_cop(p['limite'])}.")
    return (f"Vas bien en {nombre}: llevas {pct}% y {faltan} {dias}; cerrarías en "
            f"{formato_cop(p['proyectado'])} de {formato_cop(p['limite'])}.")


def proyectar_total(items: list) -> dict:
    """Suma de las proyecciones por categoría (cada una ya calculada)."""
    limite = sum(i["limite"] for i in items)
    gastado = sum(i["gastado"] for i in items)
    proyectado = sum(i["proyectado"] for i in items)
    return {
        "gastado": gastado,
        "limite": limite,
        "proyectado": proyectado,
        "pct_usado": round(gastado / limite * 100, 1) if limite > 0 else 0.0,
        "pct_proyectado": round(proyectado / limite * 100, 1) if limite > 0 else 0.0,
        "categorias_en_riesgo": sum(1 for i in items if i["estado"] in ("en_riesgo", "excedido")),
    }


def sobrante_arrastrable(limite_anterior: float, gastado_anterior: float) -> float:
    """Lo que sobró del periodo anterior (nunca negativo: un exceso no se
    descuenta del siguiente, solo el sobrante se arrastra)."""
    return max(0.0, (limite_anterior or 0.0) - (gastado_anterior or 0.0))


# ------------------------------------------------------- reparto de un ingreso

REGLA_DEFECTO = {"necesidades": 50, "deseos": 30, "ahorro": 20}


def validar_regla(regla: Optional[dict]) -> dict:
    """La regla debe sumar 100; si no, vuelve a 50/30/20."""
    if not regla:
        return dict(REGLA_DEFECTO)
    try:
        r = {k: float(regla[k]) for k in REGLA_DEFECTO}
    except (KeyError, TypeError, ValueError):
        return dict(REGLA_DEFECTO)
    if any(v < 0 for v in r.values()) or abs(sum(r.values()) - 100) > 0.01:
        return dict(REGLA_DEFECTO)
    return r


def sugerir_distribucion(monto: float, regla: Optional[dict] = None,
                         gastos_fijos: Optional[float] = None,
                         metas: Optional[list] = None,
                         sobres: Optional[list] = None) -> dict:
    """Reparte un ingreso. SOLO sugiere: no mueve plata.

    - necesidades (gastos fijos): lo que el usuario realmente tiene fijo
      (recurrentes) si se conoce; si no, regla% del ingreso.
    - lo que queda se divide entre ahorro y gasto libre en la proporción
      ahorro:deseos de la regla (20:30 por defecto => 40 % / 60 %).
    - el ahorro se reparte entre las metas proporcional a lo que cada una
      necesita por mes (sin pasarse de esa necesidad); el resto es ahorro libre.
    - el gasto libre se reparte en sobres proporcional a su límite.
    Todo en pesos enteros; el redondeo sobrante cae en el gasto libre, así la
    suma siempre es exactamente el ingreso.
    """
    monto = max(0.0, float(monto or 0))
    r = validar_regla(regla)
    avisos = []

    if gastos_fijos is not None and gastos_fijos > 0:
        necesidades = min(float(gastos_fijos), monto)
        if gastos_fijos > monto * r["necesidades"] / 100 + 0.5:
            avisos.append(
                f"Tus gastos fijos ({formato_cop(gastos_fijos)}) superan el {round(r['necesidades'])}% "
                f"de este ingreso; el ahorro y el gasto libre quedan más ajustados."
            )
    else:
        necesidades = monto * r["necesidades"] / 100
    necesidades = round(necesidades)

    resto = monto - necesidades
    denom = r["ahorro"] + r["deseos"]
    frac_ahorro = (r["ahorro"] / denom) if denom > 0 else 0.0
    ahorro_total = round(resto * frac_ahorro)

    # Metas: proporcional a la necesidad mensual de cada una, con tope en ella.
    lineas_metas = []
    metas = [m for m in (metas or []) if (m.get("aporte_mensual") or 0) > 0]
    necesidad_total = sum(m["aporte_mensual"] for m in metas)
    asignado = 0
    if metas and ahorro_total > 0:
        factor = min(1.0, ahorro_total / necesidad_total)
        for m in metas:
            v = int(round(m["aporte_mensual"] * factor))
            lineas_metas.append({"id": m.get("id"), "nombre": m.get("nombre", ""), "monto": v,
                                 "necesidad": round(m["aporte_mensual"])})
            asignado += v
        # el redondeo nunca debe pasarse del ahorro
        if asignado > ahorro_total:
            lineas_metas[-1]["monto"] -= asignado - ahorro_total
            asignado = ahorro_total
    ahorro_libre = ahorro_total - asignado

    libre = monto - necesidades - ahorro_total
    lineas_sobres = []
    sobres = [s for s in (sobres or []) if (s.get("limite") or 0) > 0]
    suma_lim = sum(s["limite"] for s in sobres)
    repartido = 0
    if sobres and libre > 0:
        for s in sobres:
            v = int(libre * s["limite"] / suma_lim)  # hacia abajo; el resto queda como "libre sin sobre"
            lineas_sobres.append({"categoria": s["categoria"], "monto": v})
            repartido += v
    libre_sin_sobre = libre - repartido

    return {
        "monto": round(monto),
        "regla": r,
        "necesidades": necesidades,
        "ahorro_total": ahorro_total,
        "metas": lineas_metas,
        "ahorro_libre": ahorro_libre,
        "gasto_libre": libre,
        "sobres": lineas_sobres,
        "gasto_libre_sin_sobre": libre_sin_sobre,
        "avisos": avisos,
    }


# --------------------------------------------------------------------- metas

def tasa_mensual(tasa_ea_pct: Optional[float]) -> float:
    """Tasa efectiva anual en % -> tasa efectiva mensual en fracción."""
    if not tasa_ea_pct or tasa_ea_pct <= 0:
        return 0.0
    return (1 + tasa_ea_pct / 100.0) ** (1 / 12) - 1


def meses_hasta(hoy, fecha) -> int:
    """Cuotas mensuales disponibles hasta la fecha: ceil(días / 30,4375), mínimo 1."""
    dias = (_a_fecha(fecha) - _a_fecha(hoy)).days
    if dias <= 0:
        return 0
    return max(1, math.ceil(dias / DIAS_MES_PROMEDIO))


def aporte_requerido(objetivo: float, saldo: float, meses: int, tasa_ea: float = 0.0) -> float:
    """Aporte mensual (al final de cada mes) para llegar a `objetivo`.
    Sin rendimiento: (objetivo - saldo) / n. Con tasa mensual r:
    PMT = (objetivo - saldo*(1+r)^n) * r / ((1+r)^n - 1)."""
    if meses <= 0:
        return max(0.0, objetivo - saldo)
    r = tasa_mensual(tasa_ea)
    if r == 0:
        return max(0.0, (objetivo - saldo) / meses)
    f = (1 + r) ** meses
    return max(0.0, (objetivo - saldo * f) * r / (f - 1))


def meses_para_meta(objetivo: float, saldo: float, aporte: float, tasa_ea: float = 0.0,
                    tope: int = 1200) -> Optional[int]:
    """Meses (enteros, hacia arriba) para llegar al objetivo aportando `aporte` al mes.
    None si nunca llega (aporte <= 0 sin rendimiento suficiente) o pasa de `tope`."""
    if saldo >= objetivo:
        return 0
    r = tasa_mensual(tasa_ea)
    if r == 0:
        if aporte <= 0:
            return None
        n = math.ceil((objetivo - saldo) / aporte)
    else:
        base = saldo + aporte / r
        if base <= 0 or objetivo + aporte / r <= 0:
            return None
        n = math.ceil(math.log((objetivo + aporte / r) / base) / math.log(1 + r) - 1e-9)
    return n if 0 <= n <= tope else None


def plan_meta(objetivo: float, saldo_actual: float, fecha_objetivo, hoy,
              ahorro_real_mensual: float = 0.0, ingreso_mensual: float = 0.0,
              gasto_mensual: float = 0.0, tasa_ea: float = 0.0) -> dict:
    """Planificador de metas inteligentes. Compara lo que HAY que ahorrar con lo
    que el usuario realmente puede (ingreso - gasto) y con lo que ahorra hoy."""
    faltante = max(0.0, objetivo - saldo_actual)
    meses = meses_hasta(hoy, fecha_objetivo) if fecha_objetivo else None
    capacidad = max(0.0, ingreso_mensual - gasto_mensual) if ingreso_mensual > 0 else None

    requerido = None
    if meses:
        requerido = aporte_requerido(objetivo, saldo_actual, meses, tasa_ea)

    # Ritmo de referencia: lo que realmente ahorra; si no ahorra, lo que podría.
    ritmo = max(0.0, ahorro_real_mensual)
    meses_a_ritmo = meses_para_meta(objetivo, saldo_actual, ritmo, tasa_ea) if ritmo > 0 or tasa_mensual(tasa_ea) > 0 else None
    extra = 100_000 if ritmo < 1_000_000 else 250_000
    meses_con_extra = meses_para_meta(objetivo, saldo_actual, ritmo + extra, tasa_ea)

    if saldo_actual >= objetivo:
        viabilidad = "lograda"
    elif fecha_objetivo is not None and meses == 0:
        viabilidad = "fecha_vencida"
    elif requerido is None or capacidad is None:
        viabilidad = "sin_datos"
    elif requerido <= capacidad * 0.8:
        viabilidad = "viable"
    elif requerido <= capacidad:
        viabilidad = "ajustada"
    else:
        viabilidad = "incompatible"

    advertencia = None
    if viabilidad == "incompatible":
        advertencia = (
            f"Necesitas ahorrar {formato_cop(requerido)} al mes, pero según tus ingresos y gastos "
            f"solo te sobran unos {formato_cop(capacidad)}. Mueve la fecha o baja el monto."
        )
    elif viabilidad == "ajustada":
        advertencia = (
            f"Es posible pero ajustado: {formato_cop(requerido)} al mes es casi todo lo que te sobra "
            f"({formato_cop(capacidad)})."
        )
    elif viabilidad == "fecha_vencida":
        advertencia = "La fecha objetivo ya pasó; elige una fecha futura."

    partes = []
    if requerido is not None and viabilidad not in ("lograda", "fecha_vencida"):
        partes.append(f"Para llegar a {formato_cop(objetivo)} en {meses} meses aporta {formato_cop(math.ceil(requerido))} al mes.")
    if meses_a_ritmo is not None and ritmo > 0:
        partes.append(f"A tu ritmo actual ({formato_cop(ritmo)}/mes) la logras en {meses_a_ritmo} meses.")
        if meses_con_extra is not None and meses_con_extra < meses_a_ritmo:
            partes.append(f"Si subes {formato_cop(extra)}, en {meses_con_extra}.")
    elif ritmo <= 0 and viabilidad not in ("lograda", "fecha_vencida"):
        partes.append("Aún no tienes un ahorro mensual registrado; empieza con el aporte sugerido.")

    return {
        "faltante": faltante,
        "meses_disponibles": meses,
        "aporte_requerido": math.ceil(requerido) if requerido is not None else None,
        "capacidad_ahorro": capacidad,
        "ahorro_real_mensual": ritmo,
        "viabilidad": viabilidad,
        "advertencia": advertencia,
        "meses_a_ritmo_actual": meses_a_ritmo,
        "extra_sugerido": extra,
        "meses_con_extra": meses_con_extra,
        "mensaje": " ".join(partes),
    }


# ------------------------------------------------------- patrimonio: descomposición

def descomponer_crecimiento(prev: dict, cur: dict, aportes_netos: float = 0.0) -> dict:
    """Descompone el cambio del patrimonio neto entre dos fotos (snapshots).

    - valorizacion: lo que ganaron (o perdieron) las inversiones y bienes por sí
      solas = cambio de activos - plata que el usuario puso (aportes netos).
    - reduccion_deuda: deuda anterior - deuda actual (negativa si la deuda creció).
    - ahorro: el resto = cambio en cuentas + aportes netos a activos, o sea la
      plata que el usuario apartó. Pagar una deuda con plata de las cuentas baja
      este rubro y sube `reduccion_deuda` en lo mismo (el neto no se mueve).
    Por construcción: ahorro + valorizacion + reduccion_deuda = cambio del neto.
    """
    d_act = cur["total_activos"] - prev["total_activos"]
    d_cta = cur["total_cuentas"] - prev["total_cuentas"]
    d_deu = cur["total_deudas"] - prev["total_deudas"]
    valorizacion = d_act - aportes_netos
    reduccion = -d_deu
    ahorro = d_cta + aportes_netos
    return {
        "mes": cur.get("mes"),
        "neto_delta": d_act + d_cta - d_deu,
        "ahorro": ahorro,
        "valorizacion": valorizacion,
        "reduccion_deuda": reduccion,
    }


def serie_descomposicion(snapshots: list, aportes_por_mes: Optional[dict] = None) -> list:
    """Una descomposición por cada par de snapshots consecutivos (ordenados por mes).
    `aportes_por_mes`: {'YYYY-MM': aportes netos a activos en ese mes}."""
    aportes_por_mes = aportes_por_mes or {}
    snaps = sorted(snapshots, key=lambda s: s["mes"])
    return [
        descomponer_crecimiento(a, b, aportes_por_mes.get(b["mes"], 0.0))
        for a, b in zip(snaps, snaps[1:])
    ]
