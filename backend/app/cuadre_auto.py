"""Cuadre con diferencia: si UNA sola causa «probable» ya calculada explica la diferencia al peso, se aplica sola.

Parte del autoarreglo: va dentro del lote (deshacible) y SOLO se queda si, al recalcular, ese mes cierra en 0. Si no cierra,
se revierte lo que se hizo y queda como antes. Causas que se aplican (nunca dos a la vez, nunca adivinando):
  · una línea del extracto que falta por importar (una sola, sin dudas) cuyo monto es justo la diferencia;
  · una copia repetida (mismo tipo, monto, día y cuenta, fuente distinta) cuando quitarla explica la diferencia. Solo se quita
    la que NO está conciliada con un extracto y la otra SÍ está respaldada por él; dos pagos idénticos de la misma fuente
    (o ninguno respaldado) son pagos reales posibles: no se tocan;
  · el extracto era de OTRA cuenta tuya (los movimientos de esa cuenta suman justo el cambio del banco y ningún renglón del
    extracto cruza con la cuenta actual).
Con varias causas probables, o ninguna exacta, no se hace nada. Cuentas de tarjeta de crédito: no (tienen su propio cuadre)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, time

from app import cuadre_encadenado as ce
from app import cuadre_extracto as cx
from app import duplicados as dup
from app import punto_partida, reasignar_extracto
from app.contabilidad import delta_saldo
from app.models import Cuenta, HistorialExtracto, Movimiento

logger = logging.getLogger(__name__)

MAX_POR_CUENTA = 2  # meses que se arreglan por cuenta y por corrida
CORRECCIONES = ("corregir_monto", "quitar_repetido", "corregir_tipo")


def _review(h) -> list[dict]:
    try:
        r = json.loads(h.review_json or "[]")
    except ValueError:
        return []
    return r if isinstance(r, list) else []


def _cierra(db, cuenta: Cuenta, historial_id: str, inicio_pp) -> bool:
    """¿El mes de ese extracto cuadra ahora (diferencia del mes < $1)?"""
    r = ce.calcular(db, cuenta, inicio_pp)
    fila = next((f for f in r["meses"] if f.get("historial_id") == historial_id), None)
    return fila is not None and abs(fila["diferencia"]) < ce.TOL


def _ventana(f: dict) -> tuple[datetime, datetime]:
    return (datetime.combine(cx.a_fecha(f["periodo_inicio"]), time.min), datetime.combine(cx.a_fecha(f["fecha_corte"]), time.max))


# ── Detección: cada una devuelve (función que aplica, cuenta donde debe cuadrar) o None ───────────────────
def _importar_linea(ctx, h, f, cuenta, inicio_pp):
    from app import autoarreglo as aa

    probables = [c for c in f["causas"] if c.get("probable")]
    if len(probables) != 1 or probables[0]["codigo"] != "falta_importar" or len(probables[0].get("lineas") or []) != 1:
        return None
    if abs(probables[0]["efecto"] - f["diferencia"]) >= ce.TOL:
        return None
    fp = probables[0]["lineas"][0].get("fingerprint")
    review = _review(h)
    item = next((i for i in review if i.get("fingerprint") == fp), None)
    if item is None or not aa._elegible(item, inicio_pp) or any(i.get("estado") in CORRECCIONES for i in review):
        return None
    if sum(1 for i in review if i.get("estado") in ce.ESTADOS_QUE_FALTAN) != 1:
        return None  # otras líneas también faltan: no es UNA sola causa

    def aplicar():
        from app.routers.conciliacion import importar_faltantes
        from app.schemas import ImportarFaltantesRequest

        categorias = {fp: item["categoria_fija"]} if item.get("categoria_fija") else {}
        importar_faltantes(h.id, ImportarFaltantesRequest(fingerprints=[fp], categorias=categorias), ctx.db, ctx.usuario)
    return aplicar, cuenta


def _quitar_copia(ctx, h, f, cuenta):
    probables = [c for c in f["causas"] if c.get("probable")]
    if not probables or any(c["codigo"] != "movimiento_de_mas" for c in probables):
        return None
    db = ctx.db
    ini, fin = _ventana(f)
    movs = db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta.id, Movimiento.fecha >= ini, Movimiento.fecha <= fin).all()
    grupos: dict[tuple, list[Movimiento]] = {}
    for m in movs:
        if delta_saldo(m) and m.tipo in ("income", "expense") and m.fecha:
            grupos.setdefault((m.tipo, round(float(m.monto or 0), 2), m.fecha.date()), []).append(m)
    pares = [g for g in grupos.values() if len(g) >= 2]
    if len(pares) != 1 or len(pares[0]) != 2:
        return None  # ningún grupo, o más de uno, o tres copias: ambiguo
    a, b = pares[0]
    if (a.fuente or "manual") == (b.fuente or "manual"):
        return None  # misma fuente: pueden ser dos pagos reales idénticos

    def respaldada(m):
        return m.conciliado_en is not None or dup.origen_de_movimiento(m) == dup.ORIGEN_EXTRACTO

    sobra = [m for m in (a, b) if not respaldada(m)]
    queda = [m for m in (a, b) if respaldada(m)]
    if len(sobra) != 1 or len(queda) != 1:
        return None
    if abs(f["diferencia"] + delta_saldo(sobra[0])) >= ce.TOL:
        return None  # quitarla no explica la diferencia
    if any(c.get("movimiento_id") not in (a.id, b.id) for c in probables):
        return None
    victima = sobra[0].id

    def aplicar():
        from app.routers.movimientos import eliminar_movimiento

        eliminar_movimiento(victima, "duplicado", db, ctx.usuario)
    return aplicar, cuenta


def _extracto_de_otra_cuenta(ctx, h, f, cuenta, cuentas):
    if any(c.get("probable") for c in f["causas"]):
        return None
    # Si alguna línea ya cruza con movimientos de ESTA cuenta, el extracto es de ella.
    if any(i.get("estado") in ("exacto", "aproximado", "completado") for i in _review(h)):
        return None
    bc = f["banco_cambio"]
    if abs(bc) < ce.TOL:
        return None
    db = ctx.db
    ini, fin = _ventana(f)
    candidatas = []
    for o in cuentas:
        if o.id == cuenta.id or o.tipo != cuenta.tipo or (o.moneda or "COP") != (cuenta.moneda or "COP"):
            continue
        cambio = sum(delta_saldo(m) for m in db.query(Movimiento).filter(
            Movimiento.cuenta_id == o.id, Movimiento.fecha >= ini, Movimiento.fecha <= fin).all()
            if not ((m.notas or "").startswith(cx.PREFIJO_INICIAL) and m.fuente == "ajuste_saldo"))
        if abs(cambio) >= ce.TOL and abs(cambio - bc) < ce.TOL:
            con_extracto = ce._extractos_con_saldo(db, o.id)[0]
            if any(ce._clave(cx.a_fecha(x.fecha_corte)) == f["mes"] for x in con_extracto):
                continue  # esa cuenta ya tiene SU extracto de ese mes
            candidatas.append(o)
    if len(candidatas) != 1:
        return None
    destino = candidatas[0]

    def aplicar():
        reasignar_extracto.cambiar(db, ctx.usuario.id, h.id, destino.id)
    return aplicar, destino


def resolver(ctx) -> dict:
    """Recorre las cuentas de ahorro con un mes que no cuadra y aplica la causa única y exacta, si la hay."""
    from app import autoarreglo as aa

    db, uid = ctx.db, ctx.uid
    inicio_pp = punto_partida.fecha_inicio(db, uid)
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == uid).order_by(Cuenta.nombre).all()
    resueltos, revertidos = 0, 0
    for cuenta in cuentas:
        if cuenta.tipo != "ahorro":
            continue
        for _ in range(MAX_POR_CUENTA):
            try:
                r = ce.calcular(db, cuenta, inicio_pp)
                malos = [x for x in r.get("meses", []) if x.get("historial_id") and x["estado"] in ce._MALOS]
                if not malos or malos[0]["estado"] != "diferencia":
                    break
                f = malos[0]
                h = db.get(HistorialExtracto, f["historial_id"])
                if h is None or h.id in ctx.excluidos or h.estado == "error":
                    break
                propuestas = [p for p in (_importar_linea(ctx, h, f, cuenta, inicio_pp),
                                          _quitar_copia(ctx, h, f, cuenta),
                                          _extracto_de_otra_cuenta(ctx, h, f, cuenta, cuentas)) if p is not None]
                if len(propuestas) != 1:  # ninguna, o varias formas de explicarlo: no se adivina
                    break
                aplicar, donde = propuestas[0]
                previas = {x.id for x in aa._filas_del_lote(db, uid, ctx.lote)}
                cambios_antes = ctx.cambios
                aplicar()
                db.expire_all()
                ctx.cerrar_fase("cuadre")
                if _cierra(db, donde, h.id, inicio_pp):
                    resueltos += 1
                    continue
                _revertir(ctx, previas, cambios_antes)
                revertidos += 1
                break
            except Exception as e:  # noqa: BLE001 - nunca frena a las demás cuentas
                db.rollback()
                logger.warning("Autoarreglo cuadre falló (usuario %s): %s", uid[:8], type(e).__name__)
                break
    return {"resueltos": resueltos, "revertidos": revertidos}


def _revertir(ctx, previas: set[str], cambios_antes: int) -> None:
    """Deshace lo que se acaba de aplicar (no cerró en 0) y lo borra del lote: como si nunca hubiera pasado."""
    from app import autoarreglo as aa

    db = ctx.db
    nuevas = [x for x in aa._filas_del_lote(db, ctx.uid, ctx.lote) if x.id not in previas]
    aa._deshacer_filas(db, ctx.uid, nuevas)
    for x in nuevas:
        db.delete(x)
    db.commit()
    ctx.foto = aa._foto(db, ctx.uid)
    ctx.cambios = cambios_antes
