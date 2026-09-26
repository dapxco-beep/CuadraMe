from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.classifier import build_model, classify
from app.database import get_db
from app.models import Cuenta, Movimiento
from app.schemas import ClasificarRequest, ClasificarResponse, MovimientoCreate, MovimientoOut

router = APIRouter(prefix="/movimientos", tags=["movimientos"])


@router.get("", response_model=list[MovimientoOut])
def listar_movimientos(
    limit: int = 100,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    return (
        db.query(Movimiento)
        .filter(Movimiento.usuario_id == usuario.id)
        .order_by(Movimiento.fecha.desc())
        .limit(limit)
        .all()
    )


@router.post("", response_model=MovimientoOut)
def crear_movimiento(
    data: MovimientoCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = (
        db.query(Cuenta)
        .filter(Cuenta.id == data.cuenta_id, Cuenta.usuario_id == usuario.id)
        .first()
    )
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    categoria = data.categoria
    if not categoria:
        historial = _movimientos_categorizados(db, usuario.id)
        modelo = build_model(historial)
        resultado = classify(data.descripcion, modelo)
        categoria = resultado["categoria"] if resultado else "Otros"

    movimiento = Movimiento(
        usuario_id=usuario.id,
        cuenta_id=data.cuenta_id,
        descripcion=data.descripcion,
        categoria=categoria,
        tipo=data.tipo,
        monto=data.monto,
        fecha=data.fecha or datetime.utcnow(),
        notas=data.notas or "",
        fuente="manual",
    )
    db.add(movimiento)

    if data.tipo == "income":
        cuenta.saldo += data.monto
    elif data.tipo == "expense":
        cuenta.saldo -= data.monto

    db.commit()
    db.refresh(movimiento)
    return movimiento


@router.delete("/{movimiento_id}")
def eliminar_movimiento(
    movimiento_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    mov = (
        db.query(Movimiento)
        .filter(Movimiento.id == movimiento_id, Movimiento.usuario_id == usuario.id)
        .first()
    )
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    db.delete(mov)
    db.commit()
    return {"ok": True}


@router.post("/clasificar", response_model=ClasificarResponse)
def clasificar_movimiento(
    data: ClasificarRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    historial = _movimientos_categorizados(db, usuario.id)
    modelo = build_model(historial)
    resultado = classify(data.descripcion, modelo)

    if resultado:
        return ClasificarResponse(
            categoria=resultado["categoria"],
            tipo=resultado["tipo"],
            confianza=resultado["confianza"],
            fuente=resultado["fuente"],
        )

    return ClasificarResponse(categoria="Otros", tipo="expense", confianza=0, fuente="default")


def _movimientos_categorizados(db: Session, usuario_id: str) -> list[dict]:
    movs = (
        db.query(Movimiento)
        .filter(Movimiento.usuario_id == usuario_id, Movimiento.categoria != "Otros")
        .all()
    )
    return [{"descripcion": m.descripcion, "categoria": m.categoria, "tipo": m.tipo} for m in movs]
