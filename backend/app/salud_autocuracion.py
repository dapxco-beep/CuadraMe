"""Autocuración SEGURA de la salud de datos (ver docs/SALUD_DE_DATOS.md).

Regla de oro: NUNCA se mueve dinero sin que la persona lo vea. Aquí solo hay acciones que no tocan saldos:
  · `crear_cuenta_tarjeta`   la cuenta «<Banco> Tarjeta» (crédito, saldo 0) y reasignar los extractos que
                             todavía no se importaron. Es un toque de la persona; no importa movimientos.
  · `reintento_diario`       una vez al día, reintenta los extractos en error por clave si la clave existe.
Lo ya importado en una cuenta equivocada solo se SUGIERE (vista previa en «Cambiar cuenta de extracto»)."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth import UsuarioActual
from app.crons import reclamar_marca
from app.cuentas_banco import CREDITO, producto_de_cuenta, producto_de_texto
from app.extractos_gmail import cuentas_del_banco
from app.models import Cuenta, ExtractoCorreo
from app.salud_datos import diagnosticar
from app.utiles import ahora_co

logger = logging.getLogger(__name__)

CLAVE_REINTENTO_DIARIO = "salud_reintento_errores"
_PENDIENTES = ("nuevo", "falta_clave", "error")


def nombre_estandar_tarjeta(banco: str) -> str:
    return f"{' '.join((banco or '').split())} Tarjeta"[:60]


def crear_cuenta_tarjeta(db: Session, usuario_id: str, banco: str) -> dict | None:
    """Crea la tarjeta de crédito del banco y reasigna a ella los extractos de tarjeta SIN importar.
    Solo para un banco del que de verdad hay extractos de tarjeta sin cuenta (si no, None: no se inventan
    cuentas). Idempotente: si ya existe una tarjeta del banco, la reutiliza.
    Devuelve {cuenta_id, nombre, creada, reasignados}."""
    pedido = " ".join((banco or "").split()).lower()
    h = next((x for x in diagnosticar(db, usuario_id)
              if x["codigo"] == "tarjeta_sin_cuenta" and x["datos"]["banco"].lower() == pedido), None)
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()
    banco_real = h["datos"]["banco"] if h else banco
    existente = next((c for c in cuentas_del_banco(banco_real, cuentas) if producto_de_cuenta(c) == CREDITO), None)
    if h is None and existente is None:
        return None
    creada = existente is None
    cuenta = existente
    if creada:
        cuenta = Cuenta(usuario_id=usuario_id, nombre=nombre_estandar_tarjeta(banco_real), tipo="credito", saldo=0)
        db.add(cuenta)
        db.flush()
    reasignados = 0
    for e in db.query(ExtractoCorreo).filter(
            ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.historial_id.is_(None),
            ExtractoCorreo.estado.in_(_PENDIENTES)).all():
        if not e.banco or not cuentas_del_banco(e.banco, [cuenta]):
            continue
        if producto_de_texto(f"{e.asunto or ''} {e.archivo or ''}") != CREDITO or e.cuenta_sugerida_id == cuenta.id:
            continue
        e.cuenta_sugerida_id = cuenta.id
        reasignados += 1
    db.commit()
    return {"cuenta_id": cuenta.id, "nombre": cuenta.nombre, "creada": creada, "reasignados": reasignados}


def reintento_diario(db: Session, usuario_id: str, email: str = "") -> dict | None:
    """Reintenta los extractos en error por clave, UNA vez al día por persona (marca en marcas_cron).
    Nunca lanza. None = hoy ya se hizo."""
    hoy = ahora_co().date().isoformat()
    try:
        if not reclamar_marca(db, usuario_id, CLAVE_REINTENTO_DIARIO, hoy):
            return None
        from app.extractos_error import reintentar_errores_clave

        return reintentar_errores_clave(db, UsuarioActual(id=usuario_id, email=email or ""))
    except Exception:  # noqa: BLE001 - una falla aquí nunca debe frenar la lectura de correos
        db.rollback()
        logger.exception("Reintento diario de extractos falló (usuario %s)", usuario_id[:8])
        return None
