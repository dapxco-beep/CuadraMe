from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.finanzas import calc_estado_recurrente
from app.models import Cuenta, Movimiento, Recurrente
from app.schemas import MarcarPagadoRequest, RecurrenteCreate, RecurrenteOut

router = APIRouter(prefix="/recurrentes", tags=["recurrentes"])


def _serializar(rec: Recurrente) -> dict:
    return {
        "id": rec.id,
        "nombre": rec.nombre,
        "monto": rec.monto,
        "tipo": rec.tipo,
        "categoria": rec.categoria,
        "cuenta_id": rec.cuenta_id,
        "dia_del_mes": rec.dia_del_mes,
        "alerta_dias_antes": rec.alerta_dias_antes,
        "ultima_vez": rec.ultima_vez,
        "notas": rec.notas,
        "activo": rec.activo,
        **calc_estado_recurrente(rec),
    }


@router.get("", response_model=list[RecurrenteOut])
def listar_recurrentes(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    recs = (
        db.query(Recurrente)
        .filter(Recurrente.usuario_id == usuario.id, Recurrente.activo.is_(True))
        .all()
    )
    serializados = [_serializar(r) for r in recs]
    return sorted(serializados, key=lambda r: r["dia_del_mes"])


@router.post("", response_model=RecurrenteOut)
def crear_recurrente(
    data: RecurrenteCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    rec = Recurrente(usuario_id=usuario.id, **data.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _serializar(rec)


@router.post("/{rec_id}/marcar_pagado", response_model=RecurrenteOut)
def marcar_pagado(
    rec_id: str,
    data: MarcarPagadoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    rec = (
        db.query(Recurrente)
        .filter(Recurrente.id == rec_id, Recurrente.usuario_id == usuario.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recurrente no encontrado")

    rec.ultima_vez = datetime.utcnow()

    if data.crear_movimiento and rec.cuenta_id:
        cuenta = (
            db.query(Cuenta)
            .filter(Cuenta.id == rec.cuenta_id, Cuenta.usuario_id == usuario.id)
            .first()
        )
        if cuenta:
            movimiento = Movimiento(
                usuario_id=usuario.id,
                cuenta_id=cuenta.id,
                descripcion=f"{rec.nombre} (recurrente)",
                categoria=rec.categoria,
                tipo=rec.tipo,
                monto=rec.monto,
                fuente="recurrente",
                notas="Registrado automáticamente",
            )
            db.add(movimiento)
            if rec.tipo == "income":
                cuenta.saldo += rec.monto
            elif rec.tipo == "expense":
                cuenta.saldo -= rec.monto

    db.commit()
    db.refresh(rec)
    return _serializar(rec)


@router.delete("/{rec_id}")
def eliminar_recurrente(
    rec_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    rec = (
        db.query(Recurrente)
        .filter(Recurrente.id == rec_id, Recurrente.usuario_id == usuario.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recurrente no encontrado")
    rec.activo = False
    db.commit()
    return {"ok": True}
