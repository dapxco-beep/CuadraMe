"""Acceso a datos de las compras a cuotas: serializar un plan y sumar lo que se
compromete cada mes (para 'En mi bolsillo' y el flujo de caja futuro)."""
from datetime import date

from sqlalchemy.orm import Session

from app.cuotas import cuota_en_mes, estado_plan
from app.fx import convertir_a_cop
from app.models import Cuenta
from app.models_cuotas import CuotaTarjeta


def serializar_plan(plan: CuotaTarjeta, hoy: date, dia_pago: int | None) -> dict:
    est = estado_plan(
        plan.total, plan.num_cuotas, plan.cuota_mensual, plan.tasa_mensual or 0,
        plan.cuotas_pagadas or 0, plan.primera_fecha, hoy, dia_pago,
    )
    return {
        "id": plan.id,
        "cuenta_id": plan.cuenta_id,
        "movimiento_id": plan.movimiento_id,
        "descripcion": plan.descripcion,
        "total": plan.total,
        "num_cuotas": plan.num_cuotas,
        "cuota_mensual": round(plan.cuota_mensual),
        "tasa_mensual": plan.tasa_mensual or 0,
        "primera_fecha": plan.primera_fecha.date().isoformat(),
        "activo": bool(plan.activo),
        **est,
    }


def planes_activos(db: Session, usuario_id: str, cuenta_id: str | None = None) -> list[tuple[CuotaTarjeta, Cuenta]]:
    q = (
        db.query(CuotaTarjeta, Cuenta)
        .join(Cuenta, Cuenta.id == CuotaTarjeta.cuenta_id)
        .filter(CuotaTarjeta.usuario_id == usuario_id, CuotaTarjeta.activo.is_(True))
    )
    if cuenta_id:
        q = q.filter(CuotaTarjeta.cuenta_id == cuenta_id)
    return q.all()


def comprometido_cuotas(db: Session, usuario_id: str, anio: int, mes: int, hoy: date) -> float:
    """Total en COP que vence en (anio, mes) por compras a cuotas activas."""
    total = 0.0
    for plan, cuenta in planes_activos(db, usuario_id):
        est = estado_plan(
            plan.total, plan.num_cuotas, plan.cuota_mensual, plan.tasa_mensual or 0,
            plan.cuotas_pagadas or 0, plan.primera_fecha, hoy, cuenta.dia_pago,
        )
        monto = cuota_en_mes(
            plan.num_cuotas, plan.cuota_mensual, est["pagadas"], plan.primera_fecha, anio, mes, cuenta.dia_pago,
        )
        total += convertir_a_cop(monto, cuenta.moneda or "COP")
    return round(total)
