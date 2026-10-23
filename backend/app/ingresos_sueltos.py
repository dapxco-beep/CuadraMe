"""Barrido de una tarjeta: ingresos falsos que ya tienen su compra buena, y pagos repetidos.

Caso de origen (tarjeta Nu): el lector viejo leyó compras como ingresos y esos movimientos quedaron sin vínculo con el
extracto (`corregir_tipo` solo toca lo que ESE extracto importó). Cuando la compra buena (gasto) ya está en la misma
tarjeta, el ingreso es un repetido falso: se borra con motivo «error» (sin fantasma) y se revierte su saldo.
Un pago repetido (mismo valor, ±1 día, uno con categoría «Pago de tarjeta» y otro sin ella) deja uno solo.

Nunca inventa: si no hay compra buena que lo respalde, el ingreso se queda (la lectura la importa y la próxima corrida lo
quita). 1:1: cada gasto respalda UN ingreso. Sin commit; quien llama lo deshace con el lote del autoarreglo."""
from __future__ import annotations

import re
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import duplicados as dup
from app.compartidos import bloquear_cuenta
from app.contabilidad import CATEGORIA_PAGO_TARJETA, MARCA_TRASLADO_PROPIO, delta_saldo
from app.models import HistorialExtracto, Movimiento
from app.reasignar_extracto import FUENTES_IMPORTADAS

TIPOS_DE_COMPRA = ("compra", "compra_en_cuotas", "cuota_manejo", "comision", "avance", "comision_servicio")
TOL = 1.0
VENTANA = timedelta(days=1, hours=23)


def _parecen_pago(m: Movimiento) -> bool:
    return ((m.categoria or "") == CATEGORIA_PAGO_TARJETA or MARCA_TRASLADO_PROPIO in (m.notas or "")
            or re.search(r"(?<![a-z])pago(?![a-z])", (m.descripcion or "").lower()) is not None)  # Mercpago no es un pago


def _palabras(t: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{4,}", (t or "").lower()) if w not in {"compra", "tarjeta", "debito", "credito"}}


def _cerca(a: Movimiento, b: Movimiento) -> bool:
    if abs(float(a.monto) - float(b.monto)) > TOL:
        return False
    dias = abs(a.fecha - b.fecha)
    # mismo valor y comercio en común: la fecha del banco puede correrse unos días (compra vs. aplicación)
    return dias <= VENTANA or (dias <= timedelta(days=4) and bool(_palabras(a.descripcion) & _palabras(b.descripcion)))


def _quitar(db: Session, cuenta, mov: Movimiento) -> None:
    cuenta = bloquear_cuenta(db, cuenta.id) or cuenta
    cuenta.saldo = round((cuenta.saldo or 0) - delta_saldo(mov), 2)
    dup.registrar_borrado(db, mov, dup.MOTIVO_ERROR)
    db.flush()
    db.delete(mov)


def _cambiar_tipo(db: Session, cuenta, mov: Movimiento, nuevo: str) -> None:
    cuenta = bloquear_cuenta(db, cuenta.id) or cuenta
    antes = delta_saldo(mov)
    mov.tipo = nuevo
    cuenta.saldo = round((cuenta.saldo or 0) + delta_saldo(mov) - antes, 2)


def _lineas_de_compra(db: Session, cuenta_id: str):
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.cuenta_id == cuenta_id).all():
        try:
            review = json.loads(h.review_json or "[]")
        except ValueError:
            continue
        for i in review if isinstance(review, list) else []:
            if i.get("tipo") == "expense" and i.get("linea_tipo") in TIPOS_DE_COMPRA and (i.get("movimiento_id") or i.get("match_id")):
                yield i


def _es_linea_de_pago(i: dict) -> bool:
    return bool(i.get("pago_tarjeta") or i.get("linea_tipo") == "pago" or re.search(r"(?<![a-z])pago(?![a-z])", (i.get("descripcion") or "").lower()))


def reabrir_pagos_huerfanos(db: Session, usuario_id: str, cuenta) -> int:
    """Una línea de PAGO del extracto de la tarjeta que quedó «completada/exacta» contra un movimiento que no está en esta tarjeta
    (de otra cuenta, o borrado) y sin otro ingreso igual en ella: el pago de la tarjeta falta. Vuelve a «faltante» (y el extracto a
    «por revisar») para que el autoarreglo la importe con el resto de lo verificado."""
    ingresos = db.query(Movimiento).filter(Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id == cuenta.id, Movimiento.tipo == "income").all()
    reabiertas = 0
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == usuario_id, HistorialExtracto.cuenta_id == cuenta.id).all():
        try:
            review = json.loads(h.review_json or "[]")
        except ValueError:
            continue
        cambio = False
        for i in review if isinstance(review, list) else []:
            if i.get("tipo") != "income" or i.get("estado") not in ("completado", "exacto", "importado") or not _es_linea_de_pago(i):
                continue
            mid = i.get("movimiento_id") or i.get("match_id")
            m = db.get(Movimiento, mid) if mid else None
            if m is not None and m.cuenta_id == cuenta.id:
                continue
            monto = float(i.get("monto") or 0)
            if any(abs(float(g.monto) - monto) <= TOL and _pago_cerca(g, i) for g in ingresos):
                continue
            for k in ("movimiento_id", "match_id"):
                i.pop(k, None)
            i["estado"] = "faltante"
            cambio = True
            reabiertas += 1
        if cambio:
            h.review_json = json.dumps(review, ensure_ascii=False)
            h.estado = "pendiente_revision"
    return reabiertas


def _pago_cerca(g: Movimiento, i: dict) -> bool:
    from app.conciliacion import parse_bank_date

    f = parse_bank_date(i.get("fecha"))
    return f is not None and abs(g.fecha - f) <= timedelta(days=4)


def quitar_pagos_fuera_de_extracto(db: Session, usuario_id: str, cuenta) -> int:
    """Un pago importado cuya fecha cae dentro del periodo de extractos de la tarjeta leídos COMPLETOS, y que NINGUNO de ellos trae
    (mismo valor ±$1 en alguna línea de ingreso), es un residuo de una lectura vieja: se quita (motivo «error», se puede deshacer)."""
    from app.conciliacion import parse_bank_date

    hists = []
    recientes: dict = {}  # de varias lecturas del MISMO corte manda la más nueva (las viejas traen líneas dudosas que ya no existen)
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == usuario_id, HistorialExtracto.cuenta_id == cuenta.id).all():
        k = str(h.fecha_corte)[:10]
        if k not in recientes or (h.creado_en or datetime.min) > (recientes[k].creado_en or datetime.min):
            recientes[k] = h
    for h in recientes.values():
        if h.lectura_completa is not True or not h.fecha_corte or not h.periodo_inicio:
            continue
        ini, fin = parse_bank_date(h.periodo_inicio), parse_bank_date(h.fecha_corte)
        try:
            review = json.loads(h.review_json or "[]")
        except ValueError:
            continue
        if ini and fin and isinstance(review, list):
            hists.append((ini, fin + timedelta(days=1), [float(i.get("monto") or 0) for i in review if i.get("tipo") == "income"]))
    quitados = 0
    for m in db.query(Movimiento).filter(Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id == cuenta.id, Movimiento.tipo == "income",
                                         Movimiento.fuente.in_(FUENTES_IMPORTADAS), Movimiento.categoria == CATEGORIA_PAGO_TARJETA).all():
        cubren = [h for h in hists if h[0] <= m.fecha < h[1]]
        if cubren and not any(abs(x - float(m.monto)) <= TOL for h in cubren for x in h[2]):
            _quitar(db, cuenta, m)
            quitados += 1
    return quitados


def barrer(db: Session, usuario_id: str, cuenta) -> dict:
    movs = db.query(Movimiento).filter(Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id == cuenta.id,
                                       Movimiento.fuente.in_(FUENTES_IMPORTADAS)).order_by(Movimiento.fecha).all()
    # Residuo del lector viejo: una «compra» de menos de $1.000 cuya descripción es solo un año («2026») es el pedazo de una fecha
    # leído como movimiento; el extracto no la trae. Se quita (queda en el historial del lote y se puede deshacer).
    basura = [m for m in movs if m.tipo == "expense" and float(m.monto) < 1000 and re.fullmatch(r"20\d\d", (m.descripcion or "").strip())]
    for m in basura:
        _quitar(db, cuenta, m)
    movs = [m for m in movs if m not in basura]
    gastos = [m for m in movs if m.tipo == "expense"]
    ingresos = [m for m in movs if m.tipo == "income"]
    quitados_compra = quitados_pago = 0
    usados: set[str] = set()
    for m in ingresos:
        if _parecen_pago(m):
            continue
        buena = next((g for g in gastos if g.id not in usados and _cerca(g, m)), None)
        if buena is not None:
            usados.add(buena.id)
            _quitar(db, cuenta, m)
            quitados_compra += 1
    pagos = [m for m in ingresos if _parecen_pago(m) and db.get(Movimiento, m.id) is not None]
    for m in pagos:
        if (m.categoria or "") == CATEGORIA_PAGO_TARJETA:
            continue
        gemelo = next((p for p in pagos if p is not m and (p.categoria or "") == CATEGORIA_PAGO_TARJETA and _cerca(p, m)), None)
        if gemelo is not None:
            _quitar(db, cuenta, m)
            quitados_pago += 1
    # El extracto dice «compra» y el movimiento enlazado quedó como ingreso (otra fecha de por medio): pasa a gasto.
    retipados = 0
    for i in _lineas_de_compra(db, cuenta.id):
        m = db.get(Movimiento, i.get("movimiento_id") or i.get("match_id"))
        if (m is not None and m.cuenta_id == cuenta.id and m.usuario_id == usuario_id and m.tipo == "income" and not _parecen_pago(m)
                and abs(float(m.monto) - float(i.get("monto") or 0)) <= TOL):
            _cambiar_tipo(db, cuenta, m, "expense")
            retipados += 1
    # Un «Pago de tarjeta» guardado como gasto dentro de la propia tarjeta es un pago: reduce la deuda (ingreso).
    pagos_corregidos = 0
    for m in db.query(Movimiento).filter(Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id == cuenta.id, Movimiento.tipo == "expense",
                                         Movimiento.categoria == CATEGORIA_PAGO_TARJETA).all():
        _cambiar_tipo(db, cuenta, m, "income")
        pagos_corregidos += 1
    return {"ingresos_falsos": quitados_compra, "pagos_repetidos": quitados_pago, "residuos": len(basura), "retipados": retipados, "reabiertos": reabrir_pagos_huerfanos(db, usuario_id, cuenta), "pagos_fuera": quitar_pagos_fuera_de_extracto(db, usuario_id, cuenta), "pagos_corregidos": pagos_corregidos}
