"""Saldo inicial automático: con cuánto empezó una cuenta, leído de su extracto más antiguo.

El problema: la app calcula el saldo de una cuenta sumando SOLO los movimientos importados. Si nadie registró con
cuánto empezó la cuenta, el saldo sale desfasado para siempre (incluso negativo en una cuenta de ahorros), aunque
los extractos digan el saldo exacto.

La regla (genérica, para cualquier usuario): si una cuenta propia (NO tarjeta) tiene un extracto con
`saldo_inicial_extracto` (origen «extracto» o «manual», que es lo que la persona confirmó) y
  - no tiene movimientos anteriores al primer día de ese periodo,
  - no tiene ya un saldo inicial registrado (automático o a mano),
  - el saldo de la cuenta no trae un pedazo «sin explicar» (la persona ya lo fijó a mano),
  - y el punto de partida del usuario no deja ese periodo en el pasado que eligió ignorar,
entonces se registra un movimiento neutro «Saldo inicial» fechado el DÍA ANTERIOR al inicio del periodo. Es neutro
(fuente `ajuste_saldo`): no cuenta como ingreso ni gasto (regla única en contabilidad.py) y se puede deshacer.

Idempotente: cada cuenta se «reclama» UNA vez con `reclamar_marca` (clave por cuenta). Si la persona lo deshace, no
se vuelve a crear. Las tarjetas de crédito quedan fuera: la semántica de su saldo está pendiente de decisión; el
cuadre encadenado ya les ofrece «Registrar saldo inicial» como sugerencia.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app import cuadre_extracto as cx
from app import punto_partida
from app.compartidos import bloquear_cuenta
from app.crons import liberar_marca, reclamar_marca
from app.models import Cuenta, HistorialExtracto

VERSION = "1"
ORIGENES_VALIDOS = ("extracto", "manual")
SUFIJO_AUTOMATICO = " · automático"


def clave_marca(cuenta_id: str) -> str:
    return f"saldo_inicial_auto:{cuenta_id}"


def _inicio_del_periodo(h: HistorialExtracto):
    """Primer día que cubre el extracto (si no lo trae, el día 1 del mes de su corte)."""
    d = cx.a_fecha(h.periodo_inicio)
    if d:
        return d
    corte = cx.a_fecha(h.fecha_corte)
    return corte.replace(day=1) if corte else None


def proponer(db: Session, cuenta: Cuenta, inicio_pp: datetime | None = None) -> dict | None:
    """Qué saldo inicial registraría la app para esta cuenta, o None si no corresponde. Solo lee."""
    if (cuenta.tipo or "") == "credito":
        return None
    candidatos = []
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.cuenta_id == cuenta.id, HistorialExtracto.estado != "error"):
        if h.saldo_inicial_extracto is None or h.saldos_origen not in ORIGENES_VALIDOS:
            continue
        inicio = _inicio_del_periodo(h)
        if inicio:
            candidatos.append((inicio, h))
    if not candidatos:
        return None
    inicio, h = min(candidatos, key=lambda x: x[0])
    monto = round(float(h.saldo_inicial_extracto), 2)
    if abs(monto) < cx.TOLERANCIA:
        return None
    if inicio_pp is not None and punto_partida.es_anterior(inicio, inicio_pp):
        return None  # la persona eligió no mirar el pasado: no se inventan saldos de antes
    _, acumulado, filas = cx._serie(db, cuenta.id)
    corte_pre = datetime.combine(inicio, time.min)
    if any(f["fecha"] is not None and f["fecha"] < corte_pre for f in filas):
        return None  # ya hay historia antes de ese extracto
    if any(f["fuente"] == "ajuste_saldo" and (f["notas"] or "").startswith("Saldo inicial") for f in filas):
        return None  # ya tiene saldo inicial (a mano, del punto de partida o automático)
    if abs((cuenta.saldo or 0.0) - (acumulado[-1] if acumulado else 0.0)) >= cx.TOLERANCIA:
        return None  # el saldo de la cuenta ya trae un valor fijado a mano
    fecha = inicio - timedelta(days=1)
    return {"cuenta_id": cuenta.id, "cuenta": cuenta.nombre, "historial_id": h.id, "monto": monto, "fecha": fecha,
            "periodo_inicio": inicio}


def texto_aviso(monto: float, fecha) -> str:
    return f"Registré con cuánto empezó tu cuenta: {cx.pesos(monto)} al {cx.fecha_texto(fecha)}."


def registrar(db: Session, cuenta: Cuenta, inicio_pp: datetime | None = None) -> dict | None:
    """Registra el saldo inicial de UNA cuenta si corresponde (una sola vez). Hace commit. None si no hizo nada."""
    if not proponer(db, cuenta, inicio_pp):
        return None
    if not reclamar_marca(db, cuenta.usuario_id, clave_marca(cuenta.id), VERSION):
        return None  # otro proceso (o una corrida anterior) ya se hizo cargo
    try:
        cuenta = bloquear_cuenta(db, cuenta.id)
        p = proponer(db, cuenta, inicio_pp)  # con la cuenta bloqueada: nada cambió entre la lectura y la escritura
        if not p:
            liberar_marca(db, cuenta.usuario_id, clave_marca(cuenta.id))
            return None
        mov = cx.crear_saldo_inicial(db, cuenta, cuenta.usuario_id, "extracto", p["fecha"], p["monto"])
        mov.notas = (mov.notas or "")[: 200 - len(SUFIJO_AUTOMATICO)] + SUFIJO_AUTOMATICO
        h = db.get(HistorialExtracto, p["historial_id"])
        if h:
            cx.registrar_cuadre(db, cuenta, h)
        db.commit()
    except Exception:
        db.rollback()
        liberar_marca(db, cuenta.usuario_id, clave_marca(cuenta.id))  # que el próximo intento lo reintente
        raise
    return {"cuenta_id": cuenta.id, "cuenta": cuenta.nombre, "movimiento_id": mov.id, "monto": p["monto"],
            "fecha": p["fecha"].isoformat(), "saldo_cuenta": cuenta.saldo, "texto": texto_aviso(p["monto"], p["fecha"])}


def registrar_todas(db: Session, usuario_id: str, inicio_pp: datetime | None = None) -> list[dict]:
    """Pasa por las cuentas PROPIAS del usuario (no las compartidas). Idempotente."""
    out = []
    for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).order_by(Cuenta.nombre).all():
        r = registrar(db, c, inicio_pp)
        if r:
            out.append(r)
    return out

