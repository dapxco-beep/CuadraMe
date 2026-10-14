"""Cuadre encadenado mes a mes: ¿en qué MES se descuadra una cuenta y por qué?

El cuadre «acumulado» (saldo del extracto contra TODO lo que hay en la cuenta) culpa a todos los meses
siguientes por un solo error. Aquí se mide cada mes por separado y se encadenan:

  banco_cambio  = saldo_final - saldo_inicial que dice el extracto de ese mes
  app_cambio    = lo que sumaron los movimientos de la cuenta dentro de ese periodo (regla única
                  `delta_saldo`, incluidos los ajustes neutros; el «saldo inicial» no es un movimiento
                  del mes: es la apertura)
  diferencia    = banco_cambio - app_cambio          (la diferencia DEL MES)
  arrastre      = saldo_inicial_banco - saldo_inicial_app   (lo que viene de meses anteriores)
  acumulada     = arrastre + diferencia = saldo_final_banco - saldo_final_app

La cadena es consistente cuando el final de un mes es el inicial del siguiente; si no, falta un extracto
o un movimiento entre ambos. Todo se RECALCULA en cada consulta; `cuadre_estado` del historial solo se
guarda como caché con fecha (y para avisar «este mes cuadraba y dejó de cuadrar»).

Convención de signo: la de la cuenta (en una tarjeta la deuda es negativa). Diferencia > 0: el banco
registró MÁS de lo que dice tu app.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from itertools import combinations

from sqlalchemy.orm import Session

from app import cuadre_extracto as cx
from app.contabilidad import delta_saldo
from app.models import Cuenta, HistorialExtracto
from app.utiles import ahora_co

TOL = cx.TOLERANCIA
MAX_LINEAS_SUBCONJUNTO = 24  # tope para la búsqueda de subconjuntos (combinaciones de hasta 3)
MAX_MESES = 48

ESTADOS_QUE_FALTAN = ("faltante", "dudoso")


def _clave(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def _siguiente(clave: str) -> str:
    a, m = int(clave[:4]), int(clave[5:7])
    return f"{a + (m == 12)}-{(m % 12) + 1:02d}"


def _etiqueta(clave: str) -> str:
    return f"{cx._MESES_LARGO[int(clave[5:7]) - 1].capitalize()} {clave[:4]}"


def _mes_nombre(clave: str) -> str:
    return cx._MESES_LARGO[int(clave[5:7]) - 1]


def _con_tono(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _corta(f) -> str:
    d = cx.a_fecha(f)
    return f"{d.day} {cx._MESES[d.month - 1]}" if d else ""


def _signo(item: dict) -> float:
    return cx._delta(float(item.get("monto") or 0), item.get("tipo"))


def _es_apertura(f: dict) -> bool:
    return (f.get("notas") or "").startswith(cx.PREFIJO_INICIAL) and f.get("fuente") == "ajuste_saldo"


# ── Subconjuntos ────────────────────────────────────────────────────────────────────────
def subconjunto_que_explica(valores: list[float], objetivo: float, max_lineas: int = 3) -> list[int] | None:
    """Índices de a lo sumo `max_lineas` valores cuya suma es `objetivo` (±tolerancia). Prefiere el más
    chico. Pura. Con más de MAX_LINEAS_SUBCONJUNTO valores solo mira los de mayor monto."""
    if abs(objetivo) < TOL or not valores:
        return None
    idx = sorted(range(len(valores)), key=lambda i: -abs(valores[i]))[:MAX_LINEAS_SUBCONJUNTO]
    for n in range(1, max_lineas + 1):
        for comb in combinations(idx, n):
            if abs(sum(valores[i] for i in comb) - objetivo) < TOL:
                return sorted(comb)
    return None


# ── Cálculo ─────────────────────────────────────────────────────────────────────────────
def _review(h: HistorialExtracto) -> list[dict]:
    try:
        r = json.loads(h.review_json or "[]")
    except ValueError:
        return []
    return r if isinstance(r, list) else []


def _extractos_con_saldo(db: Session, cuenta_id: str) -> tuple[list[HistorialExtracto], list[HistorialExtracto]]:
    """(con saldo final y fecha de corte, sin saldo) de la cuenta. Un extracto por mes de corte: el más reciente."""
    hist = [h for h in db.query(HistorialExtracto).filter(HistorialExtracto.cuenta_id == cuenta_id)
            .order_by(HistorialExtracto.creado_en).all() if h.estado != "error"]
    con: dict[str, HistorialExtracto] = {}
    sin: list[HistorialExtracto] = []
    for h in hist:
        f = cx.a_fecha(h.fecha_corte)
        if h.saldo_final_extracto is not None and f:
            con[_clave(f)] = h
        else:
            sin.append(h)
    return sorted(con.values(), key=lambda h: cx.a_fecha(h.fecha_corte)), sin


def _causas_de_linea(h: HistorialExtracto, d: float, cuenta_moneda: str) -> list[dict]:
    """Líneas del extracto sin importar cuya suma explica la diferencia `d` del mes."""
    pend = [i for i in _review(h) if i.get("estado") in ESTADOS_QUE_FALTAN and i.get("tipo") in ("income", "expense")]
    if not pend:
        return []
    valores = [_signo(i) for i in pend]
    if abs(sum(valores) - d) < TOL:
        sel = list(range(len(pend)))
    else:
        sel = subconjunto_que_explica(valores, d)
    lineas_total = [{"fecha": i.get("fecha"), "descripcion": i.get("descripcion"), "monto": i.get("monto"), "tipo": i.get("tipo"),
                     "estado": i.get("estado"), "fingerprint": i.get("fingerprint")} for i in pend]
    if sel is None:
        return [{"codigo": "lineas_sin_importar", "probable": False, "efecto": 0.0, "lineas": lineas_total[:10], "texto": (
            f"Hay {len(pend)} {'línea' if len(pend) == 1 else 'líneas'} del extracto sin importar "
            f"({cx.pesos(sum(valores))} en total), pero no explican toda la diferencia.")}]
    elegidas = [lineas_total[i] for i in sel]
    efecto = round(sum(valores[i] for i in sel), 2)
    if len(elegidas) == 1:
        l = elegidas[0]
        que = "ingreso" if l["tipo"] == "income" else "gasto"
        texto = (f"Falta importar 1 línea del extracto: {que} de {cx.pesos(l['monto'])}"
                 f"{' del ' + _corta(l['fecha']) if _corta(l['fecha']) else ''}.")
    else:
        texto = (f"Faltan importar {len(elegidas)} líneas del extracto que suman {cx.pesos(efecto)}: "
                 + "; ".join(f"{cx.pesos(l['monto'])} {_corta(l['fecha'])}".strip() for l in elegidas) + ".")
    return [{"codigo": "falta_importar", "probable": True, "efecto": efecto, "lineas": elegidas, "texto": texto}]


def _causas_de_movimientos(filas: list[dict], d: float, ini: date, fin: date, sobrantes: dict[str, dict]) -> list[dict]:
    """Movimientos de la app que el extracto no trae: uno solo cuyo monto es justo la diferencia."""
    out = []
    a, b = datetime.combine(ini, time.min), datetime.combine(fin, time.max)
    for f in filas:
        v = delta_saldo(f)
        if not v or f["fecha"] is None or _es_apertura(f):
            continue
        if a <= f["fecha"] <= b and abs(v + d) < TOL:
            desc = (f.get("descripcion") or "")[:40]
            respaldo = f["id"] in sobrantes
            out.append({"codigo": "movimiento_de_mas", "probable": True, "efecto": round(-v, 2), "movimiento_id": f["id"],
                        "texto": (f"Hay un movimiento de {cx.pesos(v)} («{desc}», {_corta(f['fecha'])}) que el extracto no trae: "
                                  "puede estar repetido o ser de otro mes." + (" El extracto no lo respalda." if respaldo else ""))})
            break
    for f in filas:
        v = delta_saldo(f)
        if not v or f["fecha"] is None or _es_apertura(f):
            continue
        fuera = (b < f["fecha"] <= b + timedelta(days=5)) or (a - timedelta(days=5) <= f["fecha"] < a)
        if fuera and abs(v - d) < TOL:
            out.append({"codigo": "otra_fecha", "probable": True, "efecto": 0.0, "movimiento_id": f["id"], "texto": (
                f"Un movimiento de {cx.pesos(v)} está fechado el {cx.fecha_texto(f['fecha'])}, pegado a este periodo: "
                "puede ser de este mes.")})
            break
    return out


def calcular(db: Session, cuenta: Cuenta, inicio_pp: datetime | None = None, *, guardar_cache: bool = False) -> dict:
    """Cuadre encadenado de UNA cuenta. Pura salvo lecturas (y la caché si `guardar_cache`; sin commit)."""
    con, sin = _extractos_con_saldo(db, cuenta.id)
    _, _, filas = cx._serie(db, cuenta.id)
    moneda = cuenta.moneda or "COP"
    base = {"cuenta_id": cuenta.id, "cuenta": cuenta.nombre, "moneda": moneda, "orientacion": cx.ORIENTACION,
            "meses": [], "sin_saldo": [], "culpables": [], "cuadra": None, "impacto": None, "saldo_corregido": None}

    # Extractos sin saldo legible (p. ej. Nu): pedir el saldo a mano, nunca inventarlo.
    from app import estado_traer

    for h in sin:
        mes = estado_traer._mes_de_historial(h)
        lineas = [cx.a_fecha(i.get("fecha")) for i in _review(h) if i.get("estado") != "sobrante"]
        ultima = max((x for x in lineas if x), default=None)
        base["sin_saldo"].append({
            "historial_id": h.id, "mes": mes, "etiqueta": _etiqueta(mes) if mes else "Extracto",
            "fecha_sugerida": ultima.isoformat() if ultima else None,
            "texto": ("Este extracto no trae el saldo y no lo invento. "
                      f"Escribe el saldo que dice tu extracto al {cx.fecha_texto(ultima) if ultima else '[fecha de corte]'} "
                      "y puedo verificar el mes.")})
    if not con:
        return base

    mov = [{"id": f["id"], "fecha": f["fecha"], "delta": delta_saldo(f), "apertura": _es_apertura(f)} for f in filas]

    def suma(desde: datetime | None, hasta: datetime | None, apertura: bool | None = None) -> float:
        t = 0.0
        for m in mov:
            if m["fecha"] is None:
                continue
            if desde is not None and m["fecha"] < desde:
                continue
            if hasta is not None and m["fecha"] > hasta:
                continue
            if apertura is not None and m["apertura"] != apertura:
                continue
            t += m["delta"]
        return t

    filas_mes: list[dict] = []
    prev = None  # fila del extracto anterior (dict con corte y banco_final)
    for h in con:
        corte = cx.a_fecha(h.fecha_corte)
        clave = _clave(corte)
        inicio = cx.a_fecha(h.periodo_inicio) or (prev["corte"] + timedelta(days=1) if prev else date(corte.year, corte.month, 1))
        if prev and inicio <= prev["corte"]:
            inicio = prev["corte"] + timedelta(days=1)
        if inicio > corte:
            inicio = date(corte.year, corte.month, 1)
        # Meses sin extracto entre el anterior y este.
        if prev:
            m = _siguiente(prev["clave"])
            n = 0
            while m < clave and n < MAX_MESES:
                filas_mes.append({"mes": m, "etiqueta": _etiqueta(m), "estado": "falta_extracto", "historial_id": None,
                                  "texto": f"Falta el extracto de {_mes_nombre(m)}: sin él no puedo comprobar ese mes.",
                                  "causas": [], "acciones": []})
                m, n = _siguiente(m), n + 1
        d_ini, d_fin = datetime.combine(inicio, time.min), datetime.combine(corte, time.max)
        app_ini = suma(None, d_ini - timedelta(microseconds=1)) + suma(d_ini, d_fin, apertura=True)
        app_cambio = suma(d_ini, d_fin, apertura=False)
        app_fin = app_ini + app_cambio
        banco_fin = float(h.saldo_final_extracto)
        sin_ini = h.saldo_inicial_extracto is None and prev is None
        if h.saldo_inicial_extracto is not None:
            banco_ini = float(h.saldo_inicial_extracto)
        elif prev:
            banco_ini = prev["banco_final"]
        else:
            banco_ini = app_ini  # sin saldo inicial: se compara todo lo acumulado
        cadena_rota = bool(prev and h.saldo_inicial_extracto is not None and abs(prev["banco_final"] - banco_ini) >= TOL)
        banco_cambio = banco_fin - banco_ini
        dif = round(banco_cambio - app_cambio, 2)
        arrastre = round(banco_ini - app_ini, 2)
        fila = {
            "mes": clave, "etiqueta": _etiqueta(clave), "estado": None, "historial_id": h.id, "periodo_inicio": inicio.isoformat(),
            "fecha_corte": corte.isoformat(), "banco_inicial": None if sin_ini else round(banco_ini, 2),
            "banco_final": round(banco_fin, 2), "banco_cambio": round(banco_cambio, 2),
            "app_inicial": round(app_ini, 2), "app_final": round(app_fin, 2), "app_cambio": round(app_cambio, 2),
            "diferencia": dif, "arrastre": arrastre, "acumulada": round(arrastre + dif, 2),
            "cadena_rota": cadena_rota, "sin_saldo_inicial": sin_ini, "causas": [], "acciones": [],
            "saldos_origen": h.saldos_origen,
        }
        # Causas del mes.
        if abs(dif) >= TOL:
            sobrantes = {i.get("match_id"): i for i in _review(h) if i.get("estado") == "sobrante"}
            fila["causas"] += _causas_de_linea(h, dif, moneda)
            fila["causas"] += _causas_de_movimientos(filas, dif, inicio, corte, sobrantes)
        antes = any(m["fecha"] is not None and m["fecha"] < d_ini for m in mov)
        hay_apertura = any(m["apertura"] for m in mov)
        if (prev is None and not antes and not hay_apertura and not sin_ini and abs(banco_ini) >= TOL
                and abs(arrastre - banco_ini) < TOL):
            fila["causas"].append({"codigo": "saldo_inicial", "probable": True, "efecto": round(banco_ini, 2), "texto": (
                f"Tu cuenta no tiene el saldo inicial de {cx.pesos(banco_ini)} con el que el banco abrió el periodo "
                f"({cx.fecha_texto(inicio)}).")})
        elif abs(arrastre) >= TOL and prev is None:
            fila["causas"].append({"codigo": "arrastre_inicial", "probable": False, "efecto": 0.0, "texto": (
                f"El saldo con el que el banco abre este extracto ({cx.pesos(banco_ini)}) no coincide con lo que suman tus "
                f"movimientos anteriores ({cx.pesos(app_ini)}).")})
        filas_mes.append(fila)
        prev = {"corte": corte, "clave": clave, "banco_final": banco_fin}

    _clasificar(filas_mes, cuenta, moneda)
    _acciones(filas_mes, cuenta)

    # Caché con fecha + memoria de «cuadraba y dejó de cuadrar».
    por_id = {h.id: h for h in con}
    for f in filas_mes:
        h = por_id.get(f.get("historial_id"))
        if not h:
            continue
        cuadra_ahora = f["estado"] == "cuadra"
        if h.cuadre_estado == "cuadra" and not cuadra_ahora and f["estado"] != "falta_extracto":
            f["dejo_de_cuadrar"] = True
        if guardar_cache and (cuadra_ahora or h.cuadre_estado != "cuadra"):
            h.cuadre_estado = "cuadra" if abs(f["acumulada"]) < TOL else "diferencia"
            h.cuadre_diferencia = f["acumulada"]
            h.cuadre_en = ahora_co()

    culp = [f for f in filas_mes if f["estado"] in ("diferencia", "solo_saldo_inicial", "cadena_rota")]
    base["meses"] = filas_mes
    base["culpables"] = [f["mes"] for f in culp]
    base["cuadra"] = not culp and all(f["estado"] in ("cuadra", "falta_extracto") and abs(f.get("acumulada") or 0) < TOL
                                      for f in filas_mes if f.get("historial_id"))
    ultimo = next((f for f in reversed(filas_mes) if f.get("historial_id")), None)
    if ultimo:
        efectos = round(sum(c["efecto"] for f in culp for c in f["causas"] if c.get("probable") and c["codigo"] != "otra_fecha"), 2)
        base["saldo_corregido"] = {
            "saldo_ultimo_extracto": ultimo["banco_final"], "saldo_app": ultimo["app_final"],
            "saldo_app_corregido": round(ultimo["app_final"] + efectos, 2), "efecto_de_las_correcciones": efectos,
            "queda_diferencia": round(ultimo["banco_final"] - (ultimo["app_final"] + efectos), 2),
            "texto": (f"Con esas correcciones tu saldo sería {cx.pesos(ultimo['app_final'] + efectos)} y el último extracto dice "
                      f"{cx.pesos(ultimo['banco_final'])}." if abs(efectos) >= TOL else None)}
    base["impacto"] = _impacto(filas_mes)
    base["resumen"] = resumen_texto(base)
    return base


def _clasificar(filas_mes: list[dict], cuenta: Cuenta, moneda: str) -> None:
    culpable_previo: dict | None = None
    primera_con_extracto = True
    for i, f in enumerate(filas_mes):
        if f["estado"] == "falta_extracto":
            continue
        dif, arr = f["diferencia"], f["arrastre"]
        etq = f["etiqueta"].split(" ")[0].lower()
        mas_menos = "más" if dif > 0 else "menos"
        tarjeta = cuenta.tipo == "credito"
        if abs(dif) >= TOL:
            f["estado"] = "diferencia"
            causa = next((c for c in f["causas"] if c.get("probable")), None)
            f["texto"] = (f"{_con_tono(etq)} no cuadra: el banco registró {cx.pesos(dif)} {mas_menos} que tu app."
                          + (f" {causa['texto']}" if causa else " No encuentro una línea que lo explique solo."))
            culpable_previo = f
            if f["cadena_rota"]:
                f["texto"] += f" Además, {_hueco(filas_mes, i, f).lower()}"
        elif f["cadena_rota"]:
            f["estado"] = "cadena_rota"
            f["texto"] = _hueco(filas_mes, i, f)
            culpable_previo = culpable_previo or f
        elif abs(arr) >= TOL and (primera_con_extracto or abs(f["acumulada"]) >= TOL):
            if primera_con_extracto and any(c["codigo"] == "saldo_inicial" for c in f["causas"]):
                f["estado"] = "solo_saldo_inicial"
                f["texto"] = (f"{_con_tono(etq)}: solo falta el saldo inicial de {cx.pesos(arr)}; los movimientos del mes cuadran.")
                culpable_previo = f
            elif primera_con_extracto:
                f["estado"] = "diferencia"
                f["texto"] = (f"{_con_tono(etq)} no cuadra por lo que venía antes: el banco abrió el periodo con "
                              f"{cx.pesos(f['banco_inicial'] or 0)} y tus movimientos suman {cx.pesos(f['app_inicial'])}.")
            else:
                f["estado"] = "arrastra"
                de = culpable_previo["etiqueta"].split(" ")[0].lower() if culpable_previo else "un mes anterior"
                f["texto"] = (f"{_con_tono(etq)} cuadra por sí solo, pero arrastra {cx.pesos(arr)} de {de}. "
                              f"Al corregir {de}, este mes queda cuadrado.")
                f["arrastra_de"] = culpable_previo["mes"] if culpable_previo else None
        else:
            f["estado"] = "cuadra"
            f["texto"] = f"{_con_tono(etq)} cuadra con tu banco."
        if tarjeta and f["estado"] == "diferencia":
            f["texto"] = f["texto"].replace("registró", "registró (en la deuda)")
        primera_con_extracto = False


def _hueco(filas_mes: list[dict], i: int, f: dict) -> str:
    ant = next((x for x in reversed(filas_mes[:i]) if x.get("historial_id")), None)
    return (f"Hueco o extracto faltante entre {ant['etiqueta'] if ant else 'el mes anterior'} y {f['etiqueta']}: "
            "el saldo final de uno no es el inicial del otro.")


def _impacto(filas_mes: list[dict]) -> str | None:
    con = [f for f in filas_mes if f.get("historial_id")]
    malos = [f for f in con if f["estado"] in ("diferencia", "cadena_rota", "solo_saldo_inicial")]
    if not malos:
        return None
    siguientes = [f for f in con if f["estado"] == "arrastra"]
    if len(malos) == 1:
        m = malos[0]
        nom = m["etiqueta"].split(" ")[0].lower()
        if siguientes:
            return f"Corrige {nom} y todos los meses siguientes quedan cuadrados."
        return f"Corrige {nom} y tu cuenta cuadra con el banco."
    nombres = ", ".join(m["etiqueta"].split(" ")[0].lower() for m in malos)
    return f"Hay {len(malos)} meses con problema ({nombres}). Corrígelos en orden: cada uno arrastra a los siguientes."


def _acciones(filas_mes: list[dict], cuenta: Cuenta) -> None:
    """Qué se puede hacer, siempre con confirmación explícita (la pantalla pide el «sí» antes de llamar)."""
    for f in filas_mes:
        if f["estado"] not in ("diferencia", "solo_saldo_inicial", "cadena_rota"):
            continue
        acc = []
        for c in f["causas"]:
            cod = c["codigo"]
            if cod == "falta_importar":
                faltantes = [l for l in c["lineas"] if l["estado"] == "faltante" and l.get("fingerprint")]
                if faltantes:
                    acc.append({"tipo": "importar_lineas", "historial_id": f["historial_id"], "fingerprints": [l["fingerprint"] for l in faltantes],
                                "texto": "Importar la línea que falta" if len(faltantes) == 1 else f"Importar las {len(faltantes)} líneas que faltan",
                                "confirmacion": ("Se agregará a tus movimientos y tu saldo cambiará en "
                                                 f"{cx.pesos(c['efecto'])}. Si te equivocas, puedes borrarla desde Movimientos.")})
                else:
                    acc.append({"tipo": "revisar_extracto", "historial_id": f["historial_id"], "texto": "Revisar las líneas dudosas",
                                "confirmacion": None})
            elif cod == "saldo_inicial":
                acc.append({"tipo": "saldo_inicial", "historial_id": f["historial_id"], "cuenta_id": cuenta.id,
                            "monto": c["efecto"], "periodo_inicio": f["periodo_inicio"], "saldo_inicial": f["banco_inicial"],
                            "texto": f"Registrar el saldo inicial de {cx.pesos(c['efecto'])} al {cx.fecha_texto(f['periodo_inicio'])}",
                            "confirmacion": "No cuenta como gasto ni ingreso y puedes deshacerlo."})
            elif cod == "movimiento_de_mas":
                acc.append({"tipo": "revisar_duplicado", "movimiento_id": c.get("movimiento_id"), "ruta": "/buscar-duplicados",
                            "texto": "Es un duplicado: revisar", "confirmacion": None})
        # Último recurso: nada lo explica y el mes tiene una diferencia.
        if f["estado"] == "diferencia" and not any(c.get("probable") for c in f["causas"]):
            acc.append({"tipo": "ajuste", "historial_id": f["historial_id"], "cuenta_id": cuenta.id, "ultimo_recurso": True,
                        "monto": f["acumulada"],
                        "texto": "Crear ajuste de saldo (último recurso)",
                        "confirmacion": ("Un ajuste tapa la diferencia sin decir de dónde viene y puede ocultar un movimiento que falta. "
                                         "Búscalo antes. No cuenta como gasto ni ingreso y puedes deshacerlo.")})
        f["acciones"] = acc


def resumen_texto(r: dict) -> str | None:
    """Una frase para «Por hacer»: el primer mes con problema, con la cifra."""
    problemas = [f for f in r["meses"] if f["estado"] in ("diferencia", "solo_saldo_inicial", "cadena_rota")]
    for f in problemas:
        for c in f["causas"]:
            if c["codigo"] == "falta_importar" and c.get("probable"):
                n = len(c["lineas"])
                return (f"{n} {'línea' if n == 1 else 'líneas'} de {_mes_nombre(f['mes'])} por {cx.pesos(c['efecto'])} sin importar: "
                        "eso es lo que descuadra tu saldo.")
    return problemas[0]["texto"] if problemas else None


def anotar_lista(db: Session, usuario_id: str, items: list[dict], inicio_pp: datetime | None = None) -> dict[str, dict]:
    """Pone `cuadre` en cada fila de «Todos los extractos» ({estado, texto, diferencia, mes}) y devuelve el cuadre
    encadenado por cuenta (solo de cuentas con extractos que traen saldo). Aislado por usuario."""
    ids = sorted({i["cuenta_id"] for i in items if i.get("cuenta_id") and i.get("historial_id")})
    if not ids:
        return {}
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id, Cuenta.id.in_(ids)).all()
    por_cuenta: dict[str, dict] = {}
    fila_de: dict[str, dict] = {}
    for c in cuentas:
        r = calcular(db, c, inicio_pp)
        por_cuenta[c.id] = r
        for f in r["meses"]:
            if f.get("historial_id"):
                fila_de[f["historial_id"]] = f
        for s in r["sin_saldo"]:
            fila_de.setdefault(s["historial_id"], {"estado": "sin_saldo", "texto": s["texto"], "diferencia": None})
    for it in items:
        f = fila_de.get(it.get("historial_id"))
        if not f:
            continue
        est = f["estado"]
        if est == "cuadra":
            it["cuadre"] = {"estado": "cuadra", "texto": "Cuadra ✓", "diferencia": 0.0}
        elif est == "arrastra":
            it["cuadre"] = {"estado": "arrastra", "texto": f"Arrastra {cx.pesos(f['arrastre'])}", "diferencia": f["arrastre"]}
        elif est == "sin_saldo":
            it["cuadre"] = {"estado": "sin_saldo", "texto": "Sin saldo para comparar", "diferencia": None}
        else:
            v = f["diferencia"] if abs(f["diferencia"]) >= TOL else f["acumulada"]
            it["cuadre"] = {"estado": "no_cuadra", "texto": f"No cuadra · {cx.pesos(v)}", "diferencia": v}
    return por_cuenta
