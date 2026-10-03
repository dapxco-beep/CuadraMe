from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.estrategia_deudas import comparar_estrategias
from app.finanzas import calc_deuda
from app.models import Cuenta, Deuda, Movimiento
from app.schemas import DeudaCreate, DeudaOut, EstrategiaOut, PagarDeudaRequest
from app.utiles import ahora_co

router = APIRouter(prefix="/deudas", tags=["deudas"])


def _serializar(deuda: Deuda) -> dict:
    return {
        "id": deuda.id,
        "nombre": deuda.nombre,
        "tipo": deuda.tipo,
        "entidad": deuda.entidad,
        "saldo_inicial": deuda.saldo_inicial,
        "saldo_actual": deuda.saldo_actual,
        "tasa_mensual": deuda.tasa_mensual,
        "cuota_mensual": deuda.cuota_mensual,
        "fecha_inicio": deuda.fecha_inicio,
        "fecha_fin": deuda.fecha_fin,
        "dia_corte": deuda.dia_corte,
        "dia_pago": deuda.dia_pago,
        "cuenta_pago_id": deuda.cuenta_pago_id,
        "notas": deuda.notas,
        "activa": deuda.activa,
        **calc_deuda(deuda),
    }


@router.get("", response_model=list[DeudaOut])
def listar_deudas(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    deudas = (
        db.query(Deuda)
        .filter(Deuda.usuario_id == usuario.id, Deuda.activa.is_(True))
        .all()
    )
    serializadas = [_serializar(d) for d in deudas]
    return sorted(serializadas, key=lambda d: d["dias_para_pago"])


@router.get("/estrategia", response_model=EstrategiaOut)
def estrategia_deudas(
    extra: float = Query(default=0, ge=0, le=1_000_000_000),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Simula avalancha vs bola de nieve con `extra` COP adicionales al mes.
    Toda la lógica vive en app/estrategia_deudas.py (función pura)."""
    deudas = (
        db.query(Deuda)
        .filter(Deuda.usuario_id == usuario.id, Deuda.activa.is_(True))
        .all()
    )
    entrada = [
        {
            "id": d.id, "nombre": d.nombre, "saldo": d.saldo_actual,
            "tasa_mensual": d.tasa_mensual, "cuota": d.cuota_mensual,
        }
        for d in deudas
    ]
    return comparar_estrategias(entrada, extra, ahora_co())


@router.post("", response_model=DeudaOut)
def crear_deuda(
    data: DeudaCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    payload = data.model_dump()
    if payload.get("saldo_actual") is None:
        payload["saldo_actual"] = payload["saldo_inicial"]
    deuda = Deuda(usuario_id=usuario.id, **payload)
    db.add(deuda)
    db.commit()
    db.refresh(deuda)
    return _serializar(deuda)


@router.post("/{deuda_id}/pagar", response_model=DeudaOut)
def pagar_deuda(
    deuda_id: str,
    data: PagarDeudaRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    deuda = db.query(Deuda).filter(Deuda.id == deuda_id, Deuda.usuario_id == usuario.id).first()
    if not deuda:
        raise HTTPException(status_code=404, detail="Deuda no encontrada")

    saldo_anterior = deuda.saldo_actual or 0
    nuevo_saldo = max(0, saldo_anterior - data.monto_pagado)
    deuda.saldo_actual = nuevo_saldo
    if nuevo_saldo == 0:
        deuda.activa = False

    if data.crear_movimiento and deuda.cuenta_pago_id:
        cuenta = (
            db.query(Cuenta)
            .filter(Cuenta.id == deuda.cuenta_pago_id, Cuenta.usuario_id == usuario.id)
            .first()
        )
        if cuenta:
            movimiento = Movimiento(
                usuario_id=usuario.id,
                cuenta_id=cuenta.id,
                descripcion=f"Pago {deuda.nombre}",
                categoria="Deudas",
                tipo="expense",
                monto=data.monto_pagado,
                fuente="manual",
                notas=f"Saldo anterior: {saldo_anterior:,.0f}. Nuevo saldo: {nuevo_saldo:,.0f}",
            )
            db.add(movimiento)
            cuenta.saldo -= data.monto_pagado

    db.commit()
    db.refresh(deuda)
    return _serializar(deuda)


@router.delete("/{deuda_id}")
def eliminar_deuda(
    deuda_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    deuda = db.query(Deuda).filter(Deuda.id == deuda_id, Deuda.usuario_id == usuario.id).first()
    if not deuda:
        raise HTTPException(status_code=404, detail="Deuda no encontrada")
    deuda.activa = False
    db.commit()
    return {"ok": True}
