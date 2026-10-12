"""«Lo que te cuesta tener tu plata»: cuánto pagas (sin notarlo) en intereses de tarjeta, cuotas de manejo,
comisiones/seguros y 4x1000, y cuánto te rinde la plata (rendimientos). Costo neto = costos - rendimientos.

Diseño igual al de consejos.py:
  - `analizar(...)` es PURA: recibe movimientos ya «efectivos» (sin traslados, pagos de tarjeta ni ajustes de
    saldo), cuentas, desgloses de extractos y pagos a tarjetas, y devuelve el análisis. Sin base ni red.
  - `analizar_usuario(db, usuario_id, desde, hasta, hoy)` lee la base (solo lectura) y llama a la pura.
Respeta el punto de partida del usuario (cargar_movs_efectivos ya lo aplica).

Orientación educativa, NO asesoría financiera: las alertas explican qué pasó y qué podrías revisar; no
recomiendan ningún producto."""
from collections import defaultdict
from datetime import date, datetime, timedelta

from app.costos_financieros import bucket_de

AVISO = "Orientación educativa, no es asesoría financiera."

BUCKETS = ("intereses", "cuota", "comisiones", "gmf")
NOMBRES_BUCKET = {
    "intereses": "Intereses de tarjeta", "cuota": "Cuota de manejo", "comisiones": "Comisiones y seguros",
    "gmf": "4x1000 (GMF)",
}
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
            "noviembre", "diciembre"]

MESES_HISTORIA = 6  # cuánto pasado se lee antes del rango pedido (para promedio y "cobro nuevo")
UMBRAL_SUBE_PCT = 30  # un costo «sube» si supera el promedio por más de esto
MIN_SUBE_PESOS = 5_000  # y la diferencia es al menos esto (no avisar por centavos)
MIN_MESES_PREVIOS = 2  # meses con movimientos antes de decir «cobro nuevo» o «cuota que antes no cobraban»
SOLO_MINIMO_VECES = 2  # extractos pagados solo con el mínimo para avisar


def _pesos(n: float) -> str:
    return "$" + f"{round(n):,.0f}".replace(",", ".")


def _mes(f) -> str:
    return f.strftime("%Y-%m")


def _mes_anterior(mes: str, n: int = 1) -> str:
    a, m = int(mes[:4]), int(mes[5:7])
    t = a * 12 + (m - 1) - n
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def _nombre_mes(mes: str) -> str:
    return f"{MESES_ES[int(mes[5:7]) - 1]} de {mes[:4]}"


def _sin_acentos(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")


def _fecha_iso(s) -> date | None:
    try:
        return date.fromisoformat(s[:10]) if s else None
    except ValueError:
        return None


def proximo_pago(cuenta: dict, desgloses_cuenta: list[dict], hoy: date) -> date | None:
    """Próxima fecha límite de pago de una tarjeta: la del último extracto si aún no pasó; si no, el día de pago."""
    for d in sorted(desgloses_cuenta, key=lambda x: x["periodo"], reverse=True):
        f = _fecha_iso(d.get("fecha_limite_pago"))
        if f and f >= hoy:
            return f
    dia = cuenta.get("dia_pago")
    if not dia:
        return None
    a, m = hoy.year, hoy.month
    for _ in range(2):
        ultimo = (date(a + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
        f = date(a, m, min(dia, ultimo))
        if f >= hoy:
            return f
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return None


def _fecha_larga(f: date) -> str:
    return f"{f.day} de {MESES_ES[f.month - 1]}"


def _alerta(id_, tipo, prioridad, titulo, texto, cifra, accion_texto, ruta, aprende=None, **extra) -> dict:
    return {"id": id_, "tipo": tipo, "prioridad": prioridad, "titulo": titulo, "texto": texto, "cifra": cifra,
            "accion": {"texto": accion_texto, "ruta": ruta}, "aprende": aprende, **extra}


# ── tabla de costos ──────────────────────────────────────────────────────────────────
def construir_tabla(movs: list[dict], desgloses: list[dict]) -> tuple[dict, dict]:
    """({(cuenta, mes, bucket): pesos}, {(cuenta, mes): pesos de mora}). Solo costos (no rendimientos aquí:
    van en el bucket 'rendimientos'). Un costo devuelto (reverso/devolución) resta."""
    tabla: dict[tuple, float] = defaultdict(float)
    mora: dict[tuple, float] = defaultdict(float)
    for m in movs:
        if m["tipo"] not in ("income", "expense"):
            continue
        b = bucket_de(m.get("categoria"), m.get("descripcion", ""))
        if b is None:
            continue
        k = (m["cuenta_id"], _mes(m["fecha"]), b)
        if b == "rendimientos":
            if m["tipo"] == "income":
                tabla[k] += m["monto"]
            continue
        tabla[k] += m["monto"] if m["tipo"] == "expense" else -m["monto"]
        if b == "intereses" and m["tipo"] == "expense" and "mora" in _sin_acentos(m.get("descripcion", "")).lower():
            mora[(m["cuenta_id"], _mes(m["fecha"]))] += m["monto"]
    for k in list(tabla):
        tabla[k] = max(0.0, tabla[k])
    # El extracto de la tarjeta dice lo que cobró el banco: si trae más que lo registrado, manda el extracto
    # (nunca se suman los dos: el cobro del extracto es el mismo que aparece como movimiento).
    for d in desgloses:
        c, mes = d["cuenta_id"], d["periodo"]
        im = d.get("intereses_mora") or 0
        piezas = {
            "intereses": (d.get("intereses_corrientes") or 0) + im if (d.get("intereses_corrientes") is not None or d.get("intereses_mora") is not None) else None,
            "cuota": d.get("cuota_manejo"),
            "comisiones": ((d.get("comisiones") or 0) + (d.get("seguros") or 0)) if (d.get("comisiones") is not None or d.get("seguros") is not None) else None,
        }
        for b, v in piezas.items():
            if v is not None and v > tabla.get((c, mes, b), 0.0):
                tabla[(c, mes, b)] = float(v)
        if im > mora.get((c, mes), 0.0):
            mora[(c, mes)] = float(im)
    return dict(tabla), dict(mora)


def _suma(tabla: dict, filtro) -> dict:
    out = {b: 0.0 for b in BUCKETS}
    out["rendimientos"] = 0.0
    for (c, mes, b), v in tabla.items():
        if filtro(c, mes):
            out[b] += v
    costos = sum(out[b] for b in BUCKETS)
    return {**{k: round(v) for k, v in out.items()}, "total": round(costos), "costo_neto": round(costos - out["rendimientos"])}


def _meses_entre(desde: date, hasta: date) -> list[str]:
    out, a, m = [], desde.year, desde.month
    while (a, m) <= (hasta.year, hasta.month):
        out.append(f"{a:04d}-{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


# ── análisis ─────────────────────────────────────────────────────────────────────────
def analizar(movs: list[dict], cuentas: dict[str, dict], desgloses: list[dict], pagos: list[dict],
             hoy: datetime, desde: date, hasta: date) -> dict:
    """movs: [{id, cuenta_id, fecha(datetime), tipo efectivo, monto COP, categoria, descripcion}].
    cuentas: {id: {nombre, tipo, dia_pago}}. desgloses: filas de DesgloseExtractoTarjeta como dict.
    pagos: [{cuenta_id, fecha, monto}] abonos a tarjetas. Devuelve el análisis completo (ver README del módulo)."""
    hoy_d = hoy.date()
    tabla, mora = construir_tabla(movs, desgloses)
    mes_hasta = _mes(hasta)
    meses_rango = _meses_entre(desde, hasta)
    anio = str(hasta.year)

    por_mes = []
    for mes in meses_rango:
        s = _suma(tabla, lambda c, m, mes=mes: m == mes)
        previo = _suma(tabla, lambda c, m, mes=mes: m == _mes_anterior(mes))
        var = None
        if previo["total"] > 0:
            var = round((s["total"] - previo["total"]) / previo["total"] * 100)
        por_mes.append({"mes": mes, **s, "mes_anterior_total": previo["total"], "variacion_pct": var})

    # promedio mensual de los meses ANTERIORES al último del rango que tuvieron algún costo
    previos = [_suma(tabla, lambda c, m, x=x: m == x)["total"] for x in sorted({m for (_, m, _) in tabla if m < mes_hasta})]
    previos = [p for p in previos if p > 0]
    promedio = round(sum(previos) / len(previos)) if previos else 0

    periodo = _suma(tabla, lambda c, m: meses_rango[0] <= m <= meses_rango[-1])
    mes_actual = _suma(tabla, lambda c, m: m == mes_hasta)
    mes_anterior = _suma(tabla, lambda c, m: m == _mes_anterior(mes_hasta))
    del_anio = _suma(tabla, lambda c, m: m[:4] == anio)

    por_cuenta = []
    ids_cuentas = sorted({c for (c, _, _) in tabla})
    for cid in ids_cuentas:
        s = _suma(tabla, lambda c, m, cid=cid: c == cid and meses_rango[0] <= m <= meses_rango[-1])
        if not s["total"] and not s["rendimientos"]:
            continue
        info = cuentas.get(cid, {})
        por_cuenta.append({
            "cuenta_id": cid, "nombre": info.get("nombre", "Cuenta"), "tipo": info.get("tipo", "ahorro"), **s,
            "meses": [{"mes": mes, "total": _suma(tabla, lambda c, m, cid=cid, mes=mes: c == cid and m == mes)["total"]}
                      for mes in meses_rango],
        })
    por_cuenta.sort(key=lambda c: -c["total"])

    tiene_datos = bool(tabla) or any(d for d in desgloses)
    actividad: dict[str, set] = defaultdict(set)  # meses con movimientos por cuenta (para saber si "antes no se cobraba")
    for m in movs:
        actividad[m["cuenta_id"]].add(_mes(m["fecha"]))
    for d in desgloses:
        actividad[d["cuenta_id"]].add(d["periodo"])
    alertas = alertas_de_costos(tabla, mora, cuentas, desgloses, pagos, hoy_d, mes_hasta, actividad)

    return {
        "aviso": AVISO, "desde": desde.isoformat(), "hasta": hasta.isoformat(), "tiene_datos": tiene_datos,
        "periodo": periodo, "mes": {"mes": mes_hasta, **mes_actual, "mes_anterior_total": mes_anterior["total"],
                                    "variacion_pct": (round((mes_actual["total"] - mes_anterior["total"]) / mes_anterior["total"] * 100)
                                                      if mes_anterior["total"] > 0 else None)},
        "anio": {"anio": int(anio), **del_anio}, "promedio_mensual": promedio, "meses": por_mes,
        "por_cuenta": por_cuenta, "alertas": alertas,
        "tipos": [{"clave": b, "nombre": NOMBRES_BUCKET[b], "periodo": periodo[b], "mes": mes_actual[b], "anio": del_anio[b]} for b in BUCKETS],
    }


def alertas_de_costos(tabla: dict, mora: dict, cuentas: dict, desgloses: list[dict], pagos: list[dict],
                      hoy: date, mes: str, actividad: dict | None = None) -> list[dict]:
    """Alertas del mes `mes` (normalmente el actual). Ids estables: tipo + cuenta/cobro + mes."""
    out: list[dict] = []
    meses_con_datos = sorted({m for (_, m, _) in tabla})
    previos = [m for m in meses_con_datos if m < mes]
    por_cuenta_desgl = defaultdict(list)
    for d in desgloses:
        por_cuenta_desgl[d["cuenta_id"]].append(d)

    def nom(cid):
        return cuentas.get(cid, {}).get("nombre", "tu cuenta")

    # 1) Intereses de mora: urgente
    for (cid, m), v in sorted(mora.items()):
        if m != mes or v <= 0:
            continue
        pago = proximo_pago(cuentas.get(cid, {}), por_cuenta_desgl.get(cid, []), hoy)
        cuando = f" y el total antes del {_fecha_larga(pago)}" if pago else ""
        out.append(_alerta(
            f"costos-mora:{cid}:{mes}", "mora", 1, f"Pagaste intereses de mora en {nom(cid)}",
            f"Te cobraron {_pesos(v)} por intereses de mora: es lo que se cobra cuando un pago llega tarde, y es más caro que "
            f"el interés normal. Ponerte al día cuanto antes evita que siga creciendo; paga lo vencido{cuando}.",
            _pesos(v), "Ver mi tarjeta", "/cuentas", "tarjeta-de-credito", cuenta_id=cid, mes=mes))

    # 2) Costo total que sube frente al promedio
    total_mes = sum(v for (c, m, b), v in tabla.items() if m == mes and b in BUCKETS)
    prev_tot = [sum(v for (c, m, b), v in tabla.items() if m == p and b in BUCKETS) for p in previos[-3:]]
    prev_tot = [p for p in prev_tot if p > 0]
    if len(prev_tot) >= 2:
        prom = sum(prev_tot) / len(prev_tot)
        if total_mes > prom * (1 + UMBRAL_SUBE_PCT / 100) and total_mes - prom >= MIN_SUBE_PESOS:
            pct = round((total_mes / prom - 1) * 100)
            out.append(_alerta(
                f"costos-sube:{mes}", "costo_sube", 2, f"Lo que te cuesta tu plata subió {pct} %",
                f"En {_nombre_mes(mes)} pagaste {_pesos(total_mes)} en intereses, cuotas, comisiones y 4x1000, contra un promedio de "
                f"{_pesos(prom)} en los meses anteriores. Mirar de dónde viene el aumento es el primer paso.",
                f"+{_pesos(total_mes - prom)}", "Ver el detalle", "/costos", "revisar-extractos", mes=mes))

    # 3) Cuota de manejo en una cuenta/tarjeta que antes no la cobraba; cobro nuevo en general
    for cid in sorted({c for (c, m, b) in tabla if m == mes}):
        # meses ANTERIORES en que esta cuenta tuvo movimientos: sin historia no se puede decir que algo «es nuevo»
        meses_cuenta_antes = [m for m in (actividad or {}).get(cid, set()) if m < mes]
        for b in BUCKETS:
            v = tabla.get((cid, mes, b), 0.0)
            if v <= 0:
                continue
            antes = [tabla.get((cid, m, b), 0.0) for m in previos]
            historia_cuenta = len(meses_cuenta_antes) >= MIN_MESES_PREVIOS
            if any(a > 0 for a in antes) or not historia_cuenta:
                continue
            if b == "cuota":
                out.append(_alerta(
                    f"costos-cuota-nueva:{cid}:{mes}", "cuota_nueva", 2, f"Te cobraron cuota de manejo en {nom(cid)}",
                    f"Este mes te cobraron {_pesos(v)} de cuota de manejo y en los meses anteriores no aparecía. Muchas tarjetas "
                    "tienen la cuota exenta si las usas lo suficiente, y los bancos suelen aceptar una solicitud de exoneración.",
                    _pesos(v), "Revisar la tarjeta", "/cuentas", "revisar-extractos", cuenta_id=cid, mes=mes))
            else:
                out.append(_alerta(
                    f"costos-nuevo:{b}:{cid}:{mes}", "cobro_nuevo", 2, f"Cobro nuevo: {NOMBRES_BUCKET[b].lower()} en {nom(cid)}",
                    f"En {_nombre_mes(mes)} aparece un cobro de {_pesos(v)} por {NOMBRES_BUCKET[b].lower()} en {nom(cid)} que no veíamos "
                    "en los meses anteriores. Si no lo reconoces, vale la pena preguntarle al banco de dónde sale.",
                    _pesos(v), "Ver el detalle", "/costos", "revisar-extractos", cuenta_id=cid, mes=mes))

    # 4) Pago solo del mínimo, repetido (necesita los extractos aplicados)
    for cid, filas in por_cuenta_desgl.items():
        marcados = []
        for d in sorted(filas, key=lambda x: x["periodo"]):
            minimo, total = d.get("pago_minimo"), d.get("pago_total")
            corte, limite = _fecha_iso(d.get("fecha_corte")), _fecha_iso(d.get("fecha_limite_pago"))
            if not (minimo and total and corte and limite) or total < minimo * 1.5:
                continue
            pagado = sum(p["monto"] for p in pagos if p["cuenta_id"] == cid and corte < p["fecha"].date() <= limite + timedelta(days=7))
            if 0 < pagado <= minimo * 1.1:
                marcados.append(d["periodo"])
        if len(marcados) >= SOLO_MINIMO_VECES and marcados[-1] >= _mes_anterior(mes, 2):
            costo = sum(v for (c, m, b), v in tabla.items() if c == cid and b == "intereses" and m >= marcados[0])
            pago = proximo_pago(cuentas.get(cid, {}), filas, hoy)
            cuando = f" Paga el total antes del {_fecha_larga(pago)}." if pago else ""
            out.append(_alerta(
                f"costos-solo-minimo:{cid}:{marcados[-1]}", "solo_minimo", 1 if costo > 0 else 2,
                f"Llevas {len(marcados)} extractos pagando solo el mínimo en {nom(cid)}",
                f"Pagar solo el mínimo evita la mora, pero el resto de la deuda sigue generando intereses. Desde {_nombre_mes(marcados[0])} "
                f"los intereses de esta tarjeta suman {_pesos(costo)}.{cuando}",
                _pesos(costo), "Ver mi tarjeta", "/cuentas", "tarjeta-de-credito", cuenta_id=cid, mes=mes))
    return sorted(out, key=lambda a: a["prioridad"])


# ── lectura de la base ───────────────────────────────────────────────────────────────
def analizar_usuario(db, usuario_id: str, desde: date, hasta: date, hoy: datetime) -> dict:
    from app import contabilidad as cont
    from app.compartidos import cuentas_ids_accesibles
    from app.fx import convertir_a_cop
    from app.informe_datos import cargar_movs_efectivos
    from app.models import Cuenta, Movimiento
    from app.models_cuotas import DesgloseExtractoTarjeta

    ids = list(cuentas_ids_accesibles(db, usuario_id))
    cuentas_db = db.query(Cuenta).filter(Cuenta.id.in_(ids)).all() if ids else []
    cuentas = {c.id: {"nombre": c.nombre, "tipo": c.tipo, "dia_pago": c.dia_pago} for c in cuentas_db}
    inicio_lectura = datetime(hasta.year, hasta.month, 1) - timedelta(days=31 * MESES_HISTORIA)
    inicio_lectura = min(inicio_lectura, datetime(desde.year, desde.month, 1), datetime(hasta.year, 1, 1))
    fin = datetime(hasta.year, hasta.month, hasta.day) + timedelta(days=1)
    movs = [m for m in cargar_movs_efectivos(db, usuario_id, inicio_lectura, fin) if inicio_lectura <= m["fecha"] < fin]

    desgloses = []
    if ids:
        for d in db.query(DesgloseExtractoTarjeta).filter(DesgloseExtractoTarjeta.cuenta_id.in_(ids)).all():
            desgloses.append({c: getattr(d, c) for c in (
                "cuenta_id", "periodo", "intereses_corrientes", "intereses_mora", "cuota_manejo", "comisiones", "seguros",
                "tasa_ea", "tasa_mv", "pago_total", "pago_minimo", "fecha_corte", "fecha_limite_pago")})
    tarjetas = [c.id for c in cuentas_db if c.tipo == "credito"]
    pagos = []
    if tarjetas:
        monedas = {c.id: c.moneda or "COP" for c in cuentas_db}
        for m in db.query(Movimiento).filter(Movimiento.cuenta_id.in_(tarjetas), Movimiento.tipo == "income",
                                             Movimiento.fecha >= inicio_lectura, Movimiento.fecha < fin).all():
            if m.fuente != cont.FUENTE_AJUSTE:
                pagos.append({"cuenta_id": m.cuenta_id, "fecha": m.fecha,
                              "monto": convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP"))})
    return analizar(movs, cuentas, desgloses, pagos, hoy, desde, hasta)
