"""Barrido de una tarjeta: ingresos falsos que ya tienen su compra buena, y pagos repetidos.

Caso de origen (tarjeta Nu): el lector viejo leyó compras como ingresos y esos movimientos quedaron sin vínculo con el
extracto (`corregir_tipo` solo toca lo que ESE extracto importó). Cuando la compra buena (gasto) ya está en la misma
tarjeta, el ingreso es un repetido falso: se borra con motivo «error» (sin fantasma) y se revierte su saldo.
Un pago repetido (mismo valor, ±1 día, uno con categoría «Pago de tarjeta» y otro sin ella) deja uno solo.

Nunca inventa: si no hay compra buena que lo respalde, el ingreso se queda (la lectura la importa y la próxima corrida lo
quita). 1:1: cada gasto respalda UN ingreso. Sin commit; quien llama lo deshace con el lote del autoarreglo."""
from __future__ import annotations

import re
from datetime import timedelta

from sqlalchemy.orm import Session

from app import duplicados as dup
from app.compartidos import bloquear_cuenta
from app.contabilidad import CATEGORIA_PAGO_TARJETA, MARCA_TRASLADO_PROPIO, delta_saldo
from app.models import Movimiento
from app.reasignar_extracto import FUENTES_IMPORTADAS

TOL = 1.0
VENTANA = timedelta(days=1, hours=23)


def _parecen_pago(m: Movimiento) -> bool:
    return ((m.categoria or "") == CATEGORIA_PAGO_TARJETA or MARCA_TRASLADO_PROPIO in (m.notas or "")
            or re.search(r"(?<![a-z])pago(?![a-z])", (m.descripcion or "").lower()) is not None)  # Mercpago no es un pago


def _cerca(a: Movimiento, b: Movimiento) -> bool:
    return abs(float(a.monto) - float(b.monto)) <= TOL and abs(a.fecha - b.fecha) <= VENTANA


def _quitar(db: Session, cuenta, mov: Movimiento) -> None:
    cuenta = bloquear_cuenta(db, cuenta.id) or cuenta
    cuenta.saldo = round((cuenta.saldo or 0) - delta_saldo(mov), 2)
    dup.registrar_borrado(db, mov, dup.MOTIVO_ERROR)
    db.flush()
    db.delete(mov)


def barrer(db: Session, usuario_id: str, cuenta) -> dict:
    movs = db.query(Movimiento).filter(Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id == cuenta.id,
                                       Movimiento.fuente.in_(FUENTES_IMPORTADAS)).order_by(Movimiento.fecha).all()
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
    return {"ingresos_falsos": quitados_compra, "pagos_repetidos": quitados_pago}
