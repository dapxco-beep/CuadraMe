"""Cargos inusuales y suscripciones activas, SIN IA: reglas simples sobre los gastos del usuario.

  - Cargo NUEVO y grande: un comercio (huella) que nunca había aparecido y cuyo monto supera 3 veces la
    mediana de los gastos del usuario.
  - Cargo RECURRENTE que cambia: el mismo comercio cobrado en 3 o más meses y que ahora cambia más de 20 %.
  - Suscripciones: mismo comercio y mismo monto en 3 o más meses seguidos. Si una sube de precio, se avisa.

Puro (sin base ni red). Recibe gastos «efectivos» (sin traslados ni pagos de tarjeta) con
{id, cuenta_id, fecha, monto, descripcion, categoria}. Los cobros bancarios (intereses, 4x1000...) se excluyen:
esos los cubre costos_bancarios.py.

Orientación educativa, no es asesoría financiera."""
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median

from app.clave_comercio import clave_comercio
from app.costos_financieros import bucket_de

MULTIPLO_MEDIANA = 3
MIN_MONTO_NUEVO = 30_000
MIN_GASTOS_HISTORIAL = 8
MIN_DIAS_HISTORIAL = 45
CAMBIO_RECURRENTE_PCT = 20
MIN_MESES_RECURRENTE = 3
TOLERANCIA_IGUAL_PCT = 2  # «mismo monto» = dentro de este margen
SUBE_SUSCRIPCION_PCT = 3
VENTANA_NUEVO_DIAS = 7
VENTANA_ULTIMO_COBRO_DIAS = 45
MONTO_RELEVANTE_PUSH = 100_000


def _pesos(n: float) -> str:
    return "$" + f"{round(n):,.0f}".replace(",", ".")


def _mes(f: datetime) -> str:
    return f.strftime("%Y-%m")


def _mes_anterior(mes: str) -> str:
    a, m = int(mes[:4]), int(mes[5:7])
    t = a * 12 + (m - 1) - 1
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def _gastos_de_comercio(movs: list[dict]) -> list[dict]:
    out = []
    for m in movs:
        if m.get("tipo", "expense") != "expense" or m["monto"] <= 0:
            continue
        if bucket_de(m.get("categoria"), m.get("descripcion", "")) is not None:
            continue
        h = clave_comercio(m.get("descripcion"))
        if not h:
            continue
        out.append({**m, "huella": h})
    return out


def _igual(a: float, b: float) -> bool:
    return abs(a - b) <= max(a, b) * TOLERANCIA_IGUAL_PCT / 100


def _serie_mensual(cobros: list[dict]) -> dict[str, float]:
    """{mes: monto del último cobro del mes}."""
    out: dict[str, float] = {}
    for c in sorted(cobros, key=lambda x: x["fecha"]):
        out[_mes(c["fecha"])] = c["monto"]
    return out


def suscripciones(gastos: list[dict], hoy: datetime) -> list[dict]:
    """Suscripciones activas: [{huella, nombre, monto, anterior, subio, meses, ultimo_cobro, cuenta_id}]."""
    por_huella = defaultdict(list)
    for g in gastos:
        por_huella[g["huella"]].append(g)
    out = []
    for h, cobros in por_huella.items():
        serie = _serie_mensual(cobros)
        ultimo = max(serie)
        ult_fecha = max(c["fecha"] for c in cobros)
        if (hoy - ult_fecha).days > VENTANA_ULTIMO_COBRO_DIAS:
            continue
        # cadena de meses seguidos hacia atrás desde el último mes con cobro
        cadena, mes = [], ultimo
        while mes in serie:
            cadena.append((mes, serie[mes]))
            mes = _mes_anterior(mes)
        if len(cadena) < MIN_MESES_RECURRENTE:
            continue
        cadena.reverse()  # cronológico
        monto_actual = cadena[-1][1]
        previos = [m for _, m in cadena[:-1]]
        if all(_igual(monto_actual, p) for p in previos):
            n_meses, anterior, subio = len(cadena), None, False
        elif len(previos) >= MIN_MESES_RECURRENTE and all(_igual(previos[0], p) for p in previos):
            n_meses, anterior = len(previos), previos[-1]
            subio = monto_actual > anterior * (1 + SUBE_SUSCRIPCION_PCT / 100)
        else:
            continue
        ultimo_cobro = max(cobros, key=lambda c: c["fecha"])
        out.append({
            "huella": h, "nombre": h.title(), "monto": round(monto_actual), "anterior": round(anterior) if anterior else None,
            "subio": subio, "meses": n_meses, "ultimo_cobro": ultimo_cobro["fecha"].date().isoformat(),
            "cuenta_id": ultimo_cobro.get("cuenta_id"), "mes": ultimo,
        })
    out.sort(key=lambda s: -s["monto"])
    return out


def detectar(movs: list[dict], hoy: datetime) -> dict:
    """{suscripciones, total_mensual_suscripciones, alertas}. Cada alerta: id estable, texto llano y acción."""
    gastos = _gastos_de_comercio(movs)
    subs = suscripciones(gastos, hoy)
    alertas: list[dict] = []

    for s in subs:
        if s["subio"]:
            alertas.append({
                "id": f"suscripcion-sube:{s['huella']}:{s['mes']}", "tipo": "suscripcion_sube", "prioridad": 2,
                "titulo": f"{s['nombre']} subió de precio",
                "texto": f"Antes pagabas {_pesos(s['anterior'])} al mes y el último cobro fue de {_pesos(s['monto'])}. "
                         "Vale la pena revisar si aún lo usas o si hay un plan más económico.",
                "cifra": f"+{_pesos(s['monto'] - s['anterior'])}",
                "accion": {"texto": "Ver mis suscripciones", "ruta": "/costos"}, "aprende": "revisar-extractos",
                "monto": s["monto"], "huella": s["huella"],
            })
    sube_ids = {s["huella"] for s in subs if s["subio"]}

    # Cargo recurrente (≥3 meses) que cambia de monto más de 20 %
    por_huella = defaultdict(list)
    for g in gastos:
        por_huella[g["huella"]].append(g)
    for h, cobros in por_huella.items():
        if h in sube_ids:
            continue
        ult = max(cobros, key=lambda c: c["fecha"])
        if (hoy - ult["fecha"]).days > VENTANA_ULTIMO_COBRO_DIAS:
            continue
        mes_ult = _mes(ult["fecha"])
        previos = {m: v for m, v in _serie_mensual([c for c in cobros if _mes(c["fecha"]) != mes_ult]).items()}
        if len(previos) < MIN_MESES_RECURRENTE:
            continue
        mediana = median(previos.values())
        if mediana > 0 and abs(ult["monto"] - mediana) / mediana * 100 > CAMBIO_RECURRENTE_PCT:
            cambio = "más alto" if ult["monto"] > mediana else "más bajo"
            alertas.append({
                "id": f"cargo-cambio:{h}:{mes_ult}", "tipo": "cargo_cambio", "prioridad": 2,
                "titulo": "Este cobro es nuevo o más alto de lo normal" if ult["monto"] > mediana else "Un cobro habitual cambió",
                "texto": f"«{h.title()}» te lo cobran todos los meses (normalmente {_pesos(mediana)}) y esta vez fue {_pesos(ult['monto'])}, "
                         f"{cambio} de lo habitual. Si no esperabas el cambio, revísalo con el comercio.",
                "cifra": _pesos(ult["monto"]), "accion": {"texto": "Ver el movimiento", "ruta": "/movimientos"},
                "aprende": "revisar-extractos", "monto": ult["monto"], "huella": h, "movimiento_id": ult.get("id"),
                "sube": ult["monto"] > mediana,
            })

    # Comercio NUEVO con un monto muy por encima de lo habitual
    if gastos:
        primera = min(g["fecha"] for g in gastos)
        montos = [g["monto"] for g in gastos]
        if len(gastos) >= MIN_GASTOS_HISTORIAL and (hoy - primera).days >= MIN_DIAS_HISTORIAL:
            med = median(montos)
            for g in sorted(gastos, key=lambda x: x["fecha"]):
                if (hoy - g["fecha"]).days > VENTANA_NUEVO_DIAS or g["fecha"] > hoy:
                    continue
                antes = [x for x in por_huella[g["huella"]] if x["fecha"] < g["fecha"]]
                if antes or g["monto"] < MIN_MONTO_NUEVO or g["monto"] <= med * MULTIPLO_MEDIANA:
                    continue
                alertas.append({
                    "id": f"cargo-inusual:{g.get('id') or g['huella'] + _mes(g['fecha'])}", "tipo": "cargo_inusual", "prioridad": 2,
                    "titulo": "Este cobro es nuevo o más alto de lo normal",
                    "texto": f"Es la primera vez que ves «{g['huella'].title()}» y el cobro fue de {_pesos(g['monto'])}, más de "
                             f"{MULTIPLO_MEDIANA} veces lo que sueles gastar en una compra ({_pesos(med)}). Si lo reconoces, no pasa nada; "
                             "si no, revísalo cuanto antes.",
                    "cifra": _pesos(g["monto"]), "accion": {"texto": "Ver el movimiento", "ruta": "/movimientos"},
                    "aprende": "revisar-extractos", "monto": g["monto"], "huella": g["huella"], "movimiento_id": g.get("id"),
                })
    vistos, unicas = set(), []
    for a in alertas:
        if a["id"] not in vistos:
            vistos.add(a["id"])
            unicas.append(a)
    return {
        "suscripciones": subs, "total_mensual_suscripciones": sum(s["monto"] for s in subs), "alertas": unicas,
    }


def detectar_usuario(db, usuario_id: str, hoy: datetime) -> dict:
    from app.informe_datos import cargar_movs_efectivos

    movs = [m for m in cargar_movs_efectivos(db, usuario_id, hoy - timedelta(days=200), hoy + timedelta(days=1))
            if m["tipo"] == "expense"]
    return detectar(movs, hoy)
