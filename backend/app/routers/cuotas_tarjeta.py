"""Compras a cuotas de una tarjeta de crédito (vista de compromiso: NO mueve saldos)."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.cuotas import calcular_cuota, primera_fecha_por_defecto
from app.cuotas_servicio import comprometido_cuotas, planes_activos, serializar_plan
from app.database import get_db
from app.models import Cuenta, Movimiento
from app.models_cuotas import CuotaTarjeta
from app.utiles import ahora_co

router = APIRouter(prefix="/cuotas-tarjeta", tags=["cuotas-tarjeta"])


class CuotaCreate(BaseModel):
    cuenta_id: str
    descripcion: str = Field(min_length=1, max_length=120)
    total: float = Field(gt=0, le=1e12)
    num_cuotas: int = Field(ge=1, le=120)
    tasa_mensual: float = Field(default=0, ge=0, le=20)  # % mensual; 0 = sin interés
    movimiento_id: Optional[str] = None
    primera_fecha: Optional[datetime] = None  # por defecto, el próximo corte
    cuota_mensual: Optional[float] = Field(default=None, gt=0)  # si el banco dio otra cuota exacta


class CuotaUpdate(BaseModel):
    descripcion: Optional[str] = Field(default=None, min_length=1, max_length=120)
    cuota_mensual: Optional[float] = Field(default=None, gt=0)
    cuotas_pagadas: Optional[int] = Field(default=None, ge=0)
    activo: Optional[bool] = None


def _tarjeta_propia(db: Session, usuario_id: str, cuenta_id: str) -> Cuenta:
    cuenta = db.query(Cuenta).filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario_id).first()
    if not cuenta or cuenta.tipo != "credito":
        raise HTTPException(status_code=404, detail="Tarjeta de crédito no encontrada")
    return cuenta


def _plan_propio(db: Session, usuario_id: str, plan_id: str) -> tuple[CuotaTarjeta, Cuenta]:
    plan = db.query(CuotaTarjeta).filter(CuotaTarjeta.id == plan_id, CuotaTarjeta.usuario_id == usuario_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Compra a cuotas no encontrada")
    cuenta = db.query(Cuenta).filter(Cuenta.id == plan.cuenta_id).first()
    return plan, cuenta


@router.get("")
def listar(
    cuenta_id: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Planes activos (de una tarjeta o de todas) + lo que vence este mes en cuotas."""
    hoy = ahora_co().date()
    planes = planes_activos(db, usuario.id, cuenta_id)
    items = [serializar_plan(p, hoy, c.dia_pago) for p, c in planes]
    items.sort(key=lambda x: (x["terminado"], x["proxima_fecha_pago"] or "9999"))
    este_mes = sum(
        i["cuota_mensual"] for i in items if i["vence_este_mes"] and not i["terminado"]
    ) if cuenta_id else comprometido_cuotas(db, usuario.id, hoy.year, hoy.month, hoy)
    return {"comprometido_mes": round(este_mes), "planes": items}


@router.post("")
def crear(
    data: CuotaCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = _tarjeta_propia(db, usuario.id, data.cuenta_id)
    if data.movimiento_id:
        mov = db.query(Movimiento).filter(
            Movimiento.id == data.movimiento_id, Movimiento.cuenta_id == cuenta.id
        ).first()
        if not mov:
            raise HTTPException(status_code=404, detail="Ese movimiento no es de esta tarjeta")
    hoy = ahora_co().date()
    cuota = data.cuota_mensual or round(calcular_cuota(data.total, data.num_cuotas, data.tasa_mensual))
    primera = data.primera_fecha or datetime.combine(primera_fecha_por_defecto(cuenta.dia_corte, hoy), datetime.min.time())
    plan = CuotaTarjeta(
        usuario_id=usuario.id, cuenta_id=cuenta.id, movimiento_id=data.movimiento_id,
        descripcion=data.descripcion.strip(), total=data.total, num_cuotas=data.num_cuotas,
        cuota_mensual=cuota, tasa_mensual=data.tasa_mensual, cuotas_pagadas=0, primera_fecha=primera, activo=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return serializar_plan(plan, hoy, cuenta.dia_pago)


@router.put("/{plan_id}")
def editar(
    plan_id: str,
    data: CuotaUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    plan, cuenta = _plan_propio(db, usuario.id, plan_id)
    cambios = data.model_dump(exclude_unset=True)
    if "cuotas_pagadas" in cambios:
        cambios["cuotas_pagadas"] = min(cambios["cuotas_pagadas"], plan.num_cuotas)
    for campo, valor in cambios.items():
        setattr(plan, campo, valor)
    db.commit()
    return serializar_plan(plan, ahora_co().date(), cuenta.dia_pago if cuenta else None)


@router.post("/{plan_id}/pagar-cuota")
def pagar_cuota(
    plan_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Marca a mano la siguiente cuota como pagada (las vencidas se marcan solas).
    Parte de las ya pagadas HOY, así no se queda por debajo de lo automático."""
    plan, cuenta = _plan_propio(db, usuario.id, plan_id)
    hoy = ahora_co().date()
    actuales = serializar_plan(plan, hoy, cuenta.dia_pago if cuenta else None)["pagadas"]
    plan.cuotas_pagadas = min(plan.num_cuotas, max(plan.cuotas_pagadas or 0, actuales) + 1)
    db.commit()
    return serializar_plan(plan, hoy, cuenta.dia_pago if cuenta else None)


@router.delete("/{plan_id}")
def eliminar(
    plan_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Borra solo el plan de cuotas: el movimiento de la compra y el saldo no se tocan."""
    plan, _ = _plan_propio(db, usuario.id, plan_id)
    db.delete(plan)
    db.commit()
    return {"ok": True}
