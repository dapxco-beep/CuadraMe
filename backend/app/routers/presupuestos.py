from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.models import Presupuesto
from app.schemas import PresupuestoCreate, PresupuestoOut

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])


@router.get("", response_model=list[PresupuestoOut])
def listar_presupuestos(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    return db.query(Presupuesto).filter(Presupuesto.usuario_id == usuario.id).all()


@router.post("", response_model=PresupuestoOut)
def crear_presupuesto(
    data: PresupuestoCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    presupuesto = Presupuesto(usuario_id=usuario.id, **data.model_dump())
    db.add(presupuesto)
    db.commit()
    db.refresh(presupuesto)
    return presupuesto


@router.delete("/{presupuesto_id}")
def eliminar_presupuesto(
    presupuesto_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    p = (
        db.query(Presupuesto)
        .filter(Presupuesto.id == presupuesto_id, Presupuesto.usuario_id == usuario.id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    db.delete(p)
    db.commit()
    return {"ok": True}
