"""Cierre de mes contra el extracto: «empecé con, ingresos, gastos, terminé con» por banco, para que concuerde con el banco.

Por cada cuenta y mes:

    Empecé con     el saldo inicial del extracto (si lo trae) o, si no, el saldo calculado al terminar el mes anterior
    + Ingresos     regla única de contabilidad.py (sin traslados ni pagos de tarjeta): los MISMOS que ve el informe
    - Gastos       idem
    ± Otros        lo que mueve el saldo sin ser ingreso ni gasto (traslados, pagos de tarjeta, ajustes), con detalle
    = Terminé con  calculado (empecé + ingresos - gastos ± otros)
    Según tu extracto  el saldo final que dice el banco  ->  «Cuadra» o «No cuadra por $D»

No duplica lógica: los movimientos salen de `informe_datos.cargar_movs_efectivos` (misma regla, mismo punto de partida,
misma moneda base) y el cuadre mes a mes de `cuadre_encadenado.calcular` (causas y acciones). Todo se recalcula en cada
consulta; solo lee.

Ventana del mes: si el extracto trae su periodo, se usa ese periodo (coincide con el mes calendario en cuentas de
ahorro; una tarjeta con corte a mitad de mes usa su propio corte). Sin extracto, el mes calendario.
Convención de signo: la de la cuenta (en una tarjeta la deuda es negativa).
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app import cuadre_encadenado as ce
from app import cuadre_extracto as cx
from app import punto_partida
from app.compartidos import cuentas_ids_accesibles
from app.contabilidad import CATEGORIA_PAGO_TARJETA, FUENTE_AJUSTE, ConvertidorBase, delta_saldo
from app.cuentas_banco import palabras_marca, sin_acentos
from app.informe_datos import cargar_movs_efectivos
from app.models import Cuenta, HistorialExtracto
from app.utiles import ahora_co

TOL = cx.TOLERANCIA
MESES_SELECTOR = 12
MAX_DETALLE_OTROS = 30
RUTA_CUADRE = ce.RUTA_CUADRE


def _clave(a: int, m: int) -> str:
    return f"{a}-{m:02d}"


def _mes_valido(mes: str) -> tuple[int, int]:
    a, m = int(mes[:4]), int(mes[5:7])
    return a, m


def _sumar(a: int, m: int, n: int) -> tuple[int, int]:
    t = a * 12 + (m - 1) + n
    return t // 12, t % 12 + 1


def meses_selector(db: Session, ids: set[str], hoy: date | None = None) -> list[dict]:
    """Los últimos 12 meses (el actual primero) y si tienen algún extracto con saldo."""
    hoy = hoy or ahora_co().date()
    con: set[str] = set()
    if ids:
        for corte, fin in db.query(HistorialExtracto.fecha_corte, HistorialExtracto.saldo_final_extracto).filter(
                HistorialExtracto.cuenta_id.in_(ids), HistorialExtracto.estado != "error"):
            d = cx.a_fecha(corte)
            if d and fin is not None:
                con.add(_clave(d.year, d.month))
    out = []
    for n in range(MESES_SELECTOR):
        a, m = _sumar(hoy.year, hoy.month, -n)
        k = _clave(a, m)
        out.append({"mes": k, "etiqueta": ce._etiqueta(k), "con_extracto": k in con})
    return out


def _banco_de(nombre: str) -> str:
    """Nombre corto del banco de una cuenta: «Nu Colombia» y «Nu Tarjeta» -> «Nu». Sin marca reconocible, el nombre."""
    marca = palabras_marca(nombre)
    palabras = [w for w in (nombre or "").split() if sin_acentos(w).strip(".,") in marca]
    return " ".join(palabras[:1]) if palabras else (nombre or "Cuenta")


def _tipo_otro(f: dict) -> str:
    if f.get("fuente") == FUENTE_AJUSTE:
        return "ajuste"
    if (f.get("categoria") or "").lower() == CATEGORIA_PAGO_TARJETA.lower():
        return "pago_tarjeta"
    return "traslado" if f.get("tipo") == "transfer" else "otro"


def _contribucion_efectiva(f: dict, ef: dict | None) -> float:
    """Cuánto del movimiento cuenta como ingreso (+) o gasto (-) en el informe, en la moneda de la cuenta."""
    if not ef:
        return 0.0
    if ef["tipo"] == "income":
        return float(ef["monto_original"] or 0)
    if ef["tipo"] == "expense":
        return -float(ef["monto_original"] or 0)
    return 0.0


def _ventana(fila: dict | None, a: int, m: int) -> tuple[date, date, bool]:
    """(desde, hasta, es_mes_calendario). Con extracto: su periodo; sin él, el mes calendario."""
    ini_cal, fin_cal = date(a, m, 1), date(a, m, calendar.monthrange(a, m)[1])
    if fila:
        ini, fin = cx.a_fecha(fila.get("periodo_inicio")), cx.a_fecha(fila.get("fecha_corte"))
        if ini and fin and ini <= fin and (fin - ini).days <= 45:
            return ini, fin, (ini == ini_cal and fin == fin_cal)
    return ini_cal, fin_cal, True


def _repetidos(filas_ventana: list[dict]) -> list[dict]:
    """Copias sobrantes de movimientos idénticos (mismo tipo, monto y día): candidatos a repetidos."""
    grupos: dict[tuple, list[dict]] = defaultdict(list)
    for f in filas_ventana:
        if delta_saldo(f):
            grupos[(f["tipo"], round(float(f["monto"] or 0), 2), f["fecha"].date() if f["fecha"] else None)].append(f)
    return [f for g in grupos.values() if len(g) > 1 for f in g[1:]]


def _cuenta_dict(db: Session, c: Cuenta, mes: str, a: int, m: int, movs_ef: dict[str, dict], conv: ConvertidorBase,
                 inicio_pp: datetime | None) -> dict | None:
    r = ce.calcular(db, c, inicio_pp)
    fila = next((f for f in r["meses"] if f.get("historial_id") and f["mes"] == mes), None)
    sin_saldo = next((s for s in r["sin_saldo"] if s.get("mes") == mes), None)
    _, acumulado, filas = cx._serie(db, c.id)
    ini, fin, mes_calendario = _ventana(fila, a, m)
    d_ini, d_fin = datetime.combine(ini, time.min), datetime.combine(fin, time.max)
    es_apertura = ce._es_apertura
    en_ventana = [f for f in filas if f["fecha"] is not None and d_ini <= f["fecha"] <= d_fin]
    if not fila and not sin_saldo and not [f for f in en_ventana if not es_apertura(f)]:
        return None  # esta cuenta no tuvo nada en este mes

    moneda = c.moneda or "COP"
    ingresos = gastos = delta_mes = 0.0
    ing_base = gas_base = 0.0
    otros: list[dict] = []
    for f in en_ventana:
        if es_apertura(f):
            continue
        ef = movs_ef.get(f["id"])
        d = delta_saldo(f)
        delta_mes += d
        contrib = _contribucion_efectiva(f, ef)
        if ef and ef["tipo"] == "income":
            ingresos += contrib
            ing_base += ef["monto"]
        elif ef and ef["tipo"] == "expense":
            gastos += -contrib
            gas_base += ef["monto"]
        resto = round(d - contrib, 2)
        if abs(resto) >= TOL:
            otros.append({"fecha": f["fecha"].date().isoformat(), "descripcion": (f.get("descripcion") or "")[:60],
                          "monto": resto, "clase": _tipo_otro(f)})
    otros_total = round(sum(o["monto"] for o in otros), 2)
    # Saldo de partida «sin explicar» (lo que la cuenta ya traía): parte del saldo calculado de TODOS los meses.
    sin_explicar = round((c.saldo or 0.0) - (acumulado[-1] if acumulado else 0.0), 2)
    previo = sum(delta_saldo(f) for f in filas if f["fecha"] is not None and f["fecha"] < d_ini)
    aperturas = sum(delta_saldo(f) for f in en_ventana if es_apertura(f))
    calculado_ini = round(sin_explicar + previo + aperturas, 2)

    if fila and fila.get("banco_inicial") is not None:
        empece, origen = float(fila["banco_inicial"]), "extracto"
    else:
        empece, origen = calculado_ini, "calculado"
    termine = round(empece + ingresos - gastos + otros_total, 2)
    segun = float(fila["banco_final"]) if fila else None
    dif = round(segun - termine, 2) if fila else None
    if fila:
        estado = "cuadra" if abs(dif) < TOL else "no_cuadra"
    else:
        estado = "sin_extracto"

    conv.contar(1, moneda)  # descubre si esta moneda no tiene tasa antes de decidir
    ok = moneda.upper() not in conv.sin_tasa
    base = (lambda v: round(conv.contar(v, moneda), 2)) if ok else (lambda v: 0.0)
    out = {
        "cuenta_id": c.id, "nombre": c.nombre, "tipo": c.tipo, "tarjeta": c.tipo == "credito", "moneda": moneda,
        "estado": estado, "sin_extracto": not fila,
        "etiqueta_extracto": None if fila else "Sin extracto",
        "motivo_sin_extracto": (sin_saldo or {}).get("texto") if sin_saldo else None,
        "periodo": {"desde": ini.isoformat(), "hasta": fin.isoformat(), "mes_completo": mes_calendario},
        "empece": round(empece, 2), "empece_origen": origen,
        "ingresos": round(ingresos, 2), "gastos": round(gastos, 2),
        "otros": otros_total, "otros_detalle": sorted(otros, key=lambda o: o["fecha"])[:MAX_DETALLE_OTROS],
        "otros_total_movimientos": len(otros),
        "termine": termine, "segun_extracto": round(segun, 2) if segun is not None else None,
        "diferencia": dif, "historial_id": fila["historial_id"] if fila else None,
        "cadena_rota": bool(fila and fila.get("cadena_rota")),
        "motivo": None, "causas": [], "acciones": [], "sin_tasa": not ok,
        # En moneda base, para sumar entre cuentas.
        "base": {"empece": base(empece), "ingresos": round(ing_base, 2), "gastos": round(gas_base, 2),
                 "otros": base(otros_total), "termine": base(termine), "diferencia": base(dif) if dif is not None else None},
        "_cambio_app": round(delta_mes, 2), "_banco_cambio": fila.get("banco_cambio") if fila else None,
        "_repetidos": _repetidos([f for f in en_ventana if not es_apertura(f)]) if estado == "no_cuadra" else [],
    }
    if fila and estado == "no_cuadra":
        out["motivo"] = fila.get("texto")
        out["causas"] = [dict(x) for x in fila.get("causas", [])]
        out["acciones"] = [dict(x) for x in fila.get("acciones", [])]
    return out


def _diagnosticar(cuentas: list[dict]) -> None:
    """Causas extra con los datos que ya hay: extracto de otra cuenta y movimientos repetidos."""
    for c in cuentas:
        if c["estado"] != "no_cuadra":
            continue
        dif = c["diferencia"]
        # 1) El extracto parece de otra cuenta: los movimientos de otra cuenta del mismo mes suman justo lo que dice el banco.
        bc = c["_banco_cambio"]
        if bc is not None and abs(bc) >= TOL and not any(x.get("probable") and x["codigo"] == "falta_importar" for x in c["causas"]):
            for o in cuentas:
                if o is c or o["moneda"] != c["moneda"] or o["tarjeta"] != c["tarjeta"]:
                    continue
                if abs(o["_cambio_app"] - bc) < TOL and abs(o["_cambio_app"]) >= TOL and o["sin_extracto"]:
                    c["causas"].insert(0, {"codigo": "extracto_de_otra_cuenta", "probable": True, "efecto": 0.0,
                                           "cuenta_sugerida_id": o["cuenta_id"], "texto": (
                        f"Los movimientos de «{o['nombre']}» de este mes suman justo lo que dice este extracto: "
                        "puede que lo hayas cargado en la cuenta equivocada.")})
                    c["acciones"].insert(0, {"tipo": "cambiar_cuenta", "historial_id": c["historial_id"], "destino_id": o["cuenta_id"],
                                             "texto": "Cambiar cuenta de extracto", "confirmacion": None})
                    break
        # 2) Movimientos repetidos: quitar las copias sobrantes cierra la diferencia.
        rep = c["_repetidos"]
        if rep and not any(x["codigo"] == "movimiento_de_mas" for x in c["causas"]):
            extra = round(sum(delta_saldo(f) for f in rep), 2)
            if abs(extra + dif) < TOL:
                c["causas"].insert(0, {"codigo": "repetidos", "probable": True, "efecto": round(-extra, 2), "texto": (
                    f"Parece que {len(rep)} {'movimiento está repetido' if len(rep) == 1 else 'movimientos están repetidos'} "
                    f"(mismo monto y día): sobran {cx.pesos(extra)}.")})
                c["acciones"].append({"tipo": "revisar_duplicado", "ruta": "/buscar-duplicados",
                                      "texto": "Revisar los repetidos", "confirmacion": None})
        if not c["motivo"]:
            c["motivo"] = "No encuentro una línea que lo explique solo."
        probable = next((x for x in c["causas"] if x.get("probable")), None)
        if probable and probable["codigo"] in ("extracto_de_otra_cuenta", "repetidos"):
            c["motivo"] = probable["texto"]
        c["sugerencia"] = next((x["texto"] for x in c["acciones"]), None)


def _resumen_banco(cuentas: list[dict]) -> dict:
    con = [c for c in cuentas if c["estado"] != "sin_extracto"]
    malas = [c for c in con if c["estado"] == "no_cuadra"]
    if malas:
        return {"estado": "no_cuadra", "diferencia": round(sum(abs(c["base"]["diferencia"] or 0) for c in malas), 2)}
    return {"estado": "cuadra" if con else "sin_extracto", "diferencia": 0.0 if con else None}


def _suma(cuentas: list[dict], campo: str) -> float:
    return round(sum(c["base"][campo] for c in cuentas), 2)


def construir(db: Session, usuario_id: str, mes: str) -> dict:
    """El cierre de `mes` (AAAA-MM) contra los extractos, de todas las cuentas accesibles del usuario."""
    a, m = _mes_valido(mes)
    ids = set(cuentas_ids_accesibles(db, usuario_id))
    hoy = ahora_co().date()
    inicio_pp = punto_partida.fecha_inicio(db, usuario_id)
    conv = ConvertidorBase.de_usuario(db, usuario_id)
    desde = datetime(a, m, 1) - timedelta(days=40)
    hasta = datetime(*_sumar(a, m, 1), 1) + timedelta(days=40)
    cargados = cargar_movs_efectivos(db, usuario_id, desde, hasta)
    movs_ef = {x["id"]: x for x in cargados}
    # La carga de movimientos y la de cuentas comparten el convertidor: las monedas sin tasa se juntan en `conv`.
    cuentas_db = db.query(Cuenta).filter(Cuenta.id.in_(ids)).order_by(Cuenta.nombre).all() if ids else []
    cuentas = [x for x in (_cuenta_dict(db, c, mes, a, m, movs_ef, conv, inicio_pp) for c in cuentas_db) if x]
    _diagnosticar(cuentas)

    grupos: dict[str, list[dict]] = {}
    nombres: dict[str, str] = {}
    for c in cuentas:
        b = _banco_de(c["nombre"])
        k = sin_acentos(b)
        nombres.setdefault(k, b)
        grupos.setdefault(k, []).append(c)
    bancos = []
    for k, lista in sorted(grupos.items(), key=lambda kv: nombres[kv[0]].lower()):
        lista.sort(key=lambda c: (c["tarjeta"], c["nombre"].lower()))  # primero la cuenta, luego su tarjeta
        r = _resumen_banco(lista)
        bancos.append({"banco": nombres[k], "cuentas": lista, **r,
                       "total": {"empece": _suma(lista, "empece"), "ingresos": _suma(lista, "ingresos"),
                                 "gastos": _suma(lista, "gastos"), "otros": _suma(lista, "otros"),
                                 "termine": _suma(lista, "termine")}})
    for c in cuentas:
        for k in ("_cambio_app", "_banco_cambio", "_repetidos"):
            c.pop(k, None)

    con_extracto = [c for c in cuentas if c["estado"] != "sin_extracto"]
    return {
        "mes": mes, "etiqueta": ce._etiqueta(mes), "parcial": mes >= _clave(hoy.year, hoy.month),
        "moneda_base": conv.base, "monedas_sin_tasa": sorted(set(conv.sin_tasa) | set(cargados.sin_tasa)),
        "meses": meses_selector(db, ids, hoy),
        "resumen_bancos": [{"banco": b["banco"], "estado": b["estado"], "diferencia": b["diferencia"]} for b in bancos],
        "bancos": bancos,
        "total": {"empece": _suma(cuentas, "empece"), "ingresos": _suma(cuentas, "ingresos"), "gastos": _suma(cuentas, "gastos"),
                  "otros": _suma(cuentas, "otros"), "termine": _suma(cuentas, "termine"), "cuentas": len(cuentas),
                  "cuadran": sum(1 for c in cuentas if c["estado"] == "cuadra"),
                  "no_cuadran": sum(1 for c in cuentas if c["estado"] == "no_cuadra"),
                  "sin_extracto": len(cuentas) - len(con_extracto)},
        "ruta_cuadre": RUTA_CUADRE,
        "hay_datos": bool(cuentas),
    }
