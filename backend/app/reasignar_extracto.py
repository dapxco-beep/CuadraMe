"""«Cambiar la cuenta de este extracto»: arregla un extracto que quedó pegado a la cuenta equivocada
(p. ej. el de la tarjeta de crédito Nu, importado en la cuenta de ahorros «Nu Colombia»).

Cómo se sabe qué movimientos importó ESE extracto (sin columna nueva):
  1. Cada línea de la revisión (`review_json`) que quedó 'importado' guarda su `movimiento_id` (desde
     este cambio; el auto-importar ya lo guardaba).
  2. Para los extractos viejos, se resuelve por la huella de la línea: el movimiento nace con
     `huella_externa = "ext:<fingerprint>#<ordinal>"`, fuente conciliacion_extracto/auto, en la cuenta del
     extracto y con el mismo monto. Se toma un movimiento por línea importada.
Lo que el extracto solo CONCILIÓ (movimientos manuales, de atajo o de correo que ya existían) NO se toca:
siguen siendo de la persona. Tampoco los de otro extracto (otro fingerprint u otra cuenta).

Los saldos siguen la regla única (contabilidad.delta_saldo): quitar un movimiento de A resta su efecto y
ponerlo en B lo suma. Una tarjeta de crédito usa el mismo signo (una compra baja el saldo; la deuda es negativa).
"""
from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import cuadre_extracto, estado_traer, saldo_inicial_auto
from app import duplicados as dup
from app.compartidos import bloquear_cuenta, cuenta_accesible, puede_editar_cuenta
from app.contabilidad import delta_saldo
from app.cuentas_banco import CREDITO, DEBITO, palabras_marca, producto_de_cuenta, producto_de_texto
from app.models import ExtractoCorreo, HistorialExtracto, HuellaOrigen, Movimiento

FUENTES_IMPORTADAS = ("conciliacion_extracto", "conciliacion_auto")


def _cargar(db: Session, usuario_id: str, historial_id: str, cuenta_id: str):
    historial = (db.query(HistorialExtracto)
                 .filter(HistorialExtracto.id == historial_id, HistorialExtracto.usuario_id == usuario_id).first())
    if not historial:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    destino = cuenta_accesible(db, usuario_id, cuenta_id)
    origen = cuenta_accesible(db, usuario_id, historial.cuenta_id)
    if (not destino or not origen or not puede_editar_cuenta(db, usuario_id, destino)
            or not puede_editar_cuenta(db, usuario_id, origen)):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return historial, origen, destino


def movimientos_del_extracto(db: Session, historial: HistorialExtracto, review: list[dict]) -> list[tuple[dict, Movimiento]]:
    """(línea, movimiento) de lo que este extracto importó y sigue en la cuenta del extracto."""
    salida: list[tuple[dict, Movimiento]] = []
    usados: set[str] = set()
    sin_id = []
    for item in (i for i in review if i.get("estado") == "importado"):
        mid = item.get("movimiento_id")
        mov = (db.query(Movimiento).filter(Movimiento.id == mid, Movimiento.usuario_id == historial.usuario_id,
                                           Movimiento.cuenta_id == historial.cuenta_id,
                                           Movimiento.fuente.in_(FUENTES_IMPORTADAS)).first()) if mid else None
        if mov is not None and mov.id not in usados:
            usados.add(mov.id)
            salida.append((item, mov))
        elif not mid:
            sin_id.append(item)
    for item in sin_id:
        fp = item.get("fingerprint")
        if not fp:
            continue
        candidatos = (db.query(Movimiento)
                      .filter(Movimiento.usuario_id == historial.usuario_id, Movimiento.cuenta_id == historial.cuenta_id,
                              Movimiento.fuente.in_(FUENTES_IMPORTADAS), Movimiento.huella_externa.like(f"ext:{fp}#%"))
                      .order_by(Movimiento.huella_externa).all())
        for mov in candidatos:
            if mov.id in usados or abs(float(mov.monto or 0) - float(item.get("monto") or 0)) > 0.01:
                continue
            usados.add(mov.id)
            salida.append((item, mov))
            break
    return salida


def _equivalente(db: Session, usuario_id: str, destino_id: str, mov: Movimiento, excluir: set[str]) -> Movimiento | None:
    """Un movimiento que YA está en la cuenta destino y es este mismo (mismo extracto subido antes allí)."""
    for c in db.query(Movimiento).filter(Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id == destino_id).all():
        if c.id in excluir or c.id == mov.id:
            continue
        if mov.huella_externa and c.huella_externa == mov.huella_externa:
            return c
        if c.tipo != mov.tipo or abs(float(c.monto or 0) - float(mov.monto or 0)) > 0.5:
            continue
        if not c.fecha or not mov.fecha or c.fecha.date() != mov.fecha.date():
            continue
        sim = dup.similitud_comercio(c.descripcion, mov.descripcion)
        if sim is None or sim >= 0.75:
            return c
    return None


def _plan(db: Session, usuario_id: str, historial, origen, destino) -> dict:
    review = json.loads(historial.review_json or "[]")
    pares = movimientos_del_extracto(db, historial, review) if origen.id != destino.id else []
    ids = {m.id for _, m in pares}
    mover, duplicados = [], []
    reservados: set[str] = set()
    for item, mov in pares:
        igual = _equivalente(db, usuario_id, destino.id, mov, ids | reservados)
        if igual is not None:
            reservados.add(igual.id)
            duplicados.append((item, mov, igual))
        else:
            mover.append((item, mov))
    quita = sum(delta_saldo(m) for _, m in mover) + sum(delta_saldo(m) for _, m, _ in duplicados)
    pone = sum(delta_saldo(m) for _, m in mover)
    return dict(review=review, mover=mover, duplicados=duplicados,
                saldo_origen=(origen.saldo or 0) - quita, saldo_destino=(destino.saldo or 0) + pone)


def _misma_moneda(origen, destino, plan) -> None:
    if (plan["mover"] or plan["duplicados"]) and (origen.moneda or "COP") != (destino.moneda or "COP"):
        raise HTTPException(status_code=400, detail="Las dos cuentas manejan monedas distintas; no se pueden pasar los movimientos.")


def _lado(c, antes: float, despues: float) -> dict:
    return {"id": c.id, "nombre": c.nombre, "saldo_antes": antes, "saldo_despues": despues}


def previa(db: Session, usuario_id: str, historial_id: str, cuenta_id: str) -> dict:
    historial, origen, destino = _cargar(db, usuario_id, historial_id, cuenta_id)
    plan = _plan(db, usuario_id, historial, origen, destino)
    _misma_moneda(origen, destino, plan)
    return {
        "movera": len(plan["mover"]), "duplicados": len(plan["duplicados"]), "estado": historial.estado,
        "ya_en_esa_cuenta": origen.id == destino.id,
        "origen": _lado(origen, origen.saldo or 0, plan["saldo_origen"]),
        "destino": _lado(destino, destino.saldo or 0, plan["saldo_destino"]),
    }


def cambiar(db: Session, usuario_id: str, historial_id: str, cuenta_id: str) -> dict:
    """Una sola transacción (commit al final). Idempotente: con el extracto ya en esa cuenta no hace nada."""
    historial, origen, destino = _cargar(db, usuario_id, historial_id, cuenta_id)
    if origen.id == destino.id:
        return {"ok": True, "movidos": 0, "duplicados": 0, "sin_cambios": True,
                "origen": _lado(origen, origen.saldo or 0, origen.saldo or 0),
                "destino": _lado(destino, destino.saldo or 0, destino.saldo or 0)}
    # Bloqueo de ambas cuentas siempre en el mismo orden (por id), como mover-masivo.
    bloqueadas = {cid: bloquear_cuenta(db, cid) for cid in sorted((origen.id, destino.id))}
    origen, destino = bloqueadas[origen.id], bloqueadas[destino.id]
    plan = _plan(db, usuario_id, historial, origen, destino)
    _misma_moneda(origen, destino, plan)
    antes_o, antes_d = origen.saldo or 0, destino.saldo or 0
    review, viejo = plan["review"], origen.id

    for item, mov in plan["mover"]:
        origen.saldo -= delta_saldo(mov)
        destino.saldo += delta_saldo(mov)
        mov.cuenta_id = destino.id
        item["movimiento_id"] = mov.id
    ids_movidos = [m.id for _, m in plan["mover"]]
    if ids_movidos:  # las huellas llevan la foto de la cuenta: se mueven con el movimiento
        db.query(HuellaOrigen).filter(HuellaOrigen.movimiento_id.in_(ids_movidos)).update(
            {HuellaOrigen.cuenta_id: destino.id}, synchronize_session=False)

    # Ya estaba en la cuenta nueva (el mismo extracto subido antes allí): no se duplica; el de la cuenta
    # equivocada se quita y el canal «extracto» queda anotado en el que ya existía.
    for item, mov, igual in plan["duplicados"]:
        origen.saldo -= delta_saldo(mov)
        huella = mov.huella_externa
        dup.olvidar_movimiento(db, mov)
        db.delete(mov)
        dup.registrar_canal(db, igual, dup.ORIGEN_EXTRACTO, huella)
        item["estado"] = "exacto"
        item["duplicado_evitado"] = True
        item.pop("movimiento_id", None)

    # Líneas que la persona descartó en la cuenta anterior: el descarte las sigue a la cuenta nueva.
    for fp in [i["fingerprint"] for i in review if i.get("fingerprint")]:
        db.query(HuellaOrigen).filter(
            HuellaOrigen.usuario_id == usuario_id, HuellaOrigen.cuenta_id == viejo, HuellaOrigen.estado == "descartado",
            HuellaOrigen.huella.like(f"ext:{fp}#%")).update({HuellaOrigen.cuenta_id: destino.id}, synchronize_session=False)

    historial.cuenta_id = destino.id
    for e in db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.historial_id == historial.id).all():
        e.cuenta_sugerida_id = destino.id
    historial.review_json = json.dumps(review, default=str)
    if plan["duplicados"]:
        estado_traer.sincronizar_contadores(historial, review)
    # El cuadre se mide contra la cuenta nueva (lo anterior era de la otra cuenta).
    historial.cuadre_estado = historial.cuadre_diferencia = historial.cuadre_en = None
    if not any(i.get("estado") in ("faltante", "dudoso", "corregir_monto", "quitar_repetido", "corregir_tipo") for i in review):
        cuadre_extracto.registrar_cuadre(db, destino, historial)
    db.commit()
    # El extracto salió de una cuenta y entró en otra: el más antiguo de AMBAS pudo cambiar → se recalculan las dos.
    ajustes = saldo_inicial_auto.refrescar_de_usuario(db, usuario_id, [origen.id, destino.id])
    return {"ok": True, "movidos": len(plan["mover"]), "duplicados": len(plan["duplicados"]), "sin_cambios": False,
            "origen": _lado(origen, antes_o, origen.saldo), "destino": _lado(destino, antes_d, destino.saldo),
            "saldo_inicial_auto": ajustes}


def sugerir_cuenta_credito(historial, cuenta, cuentas: list, texto: str) -> dict | None:
    """«Parece de tu tarjeta de crédito»: el extracto está en una cuenta de ahorros/débito pero el correo, el
    asunto o el archivo hablan de tarjeta de crédito, y hay UNA tarjeta de crédito del mismo banco."""
    if historial is None or cuenta is None or producto_de_cuenta(cuenta) != DEBITO:
        return None
    if producto_de_texto(texto) != CREDITO:
        return None
    marca = palabras_marca(cuenta.nombre)
    otras = [c for c in cuentas if c.id != cuenta.id and producto_de_cuenta(c) == CREDITO
             and (c.moneda or "COP") == (cuenta.moneda or "COP") and marca & palabras_marca(c.nombre)]
    if len(otras) != 1:
        return None
    return {"cuenta_id": otras[0].id, "nombre": otras[0].nombre}
