from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.models import Cuenta
from app.schemas import CuentaCreate, CuentaOut

router = APIRouter(prefix="/cuentas", tags=["cuentas"])


@router.get("", response_model=list[CuentaOut])
def listar_cuentas(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    return db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()


@router.post("", response_model=CuentaOut)
def crear_cuenta(
    data: CuentaCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = Cuenta(usuario_id=usuario.id, **data.model_dump())
    db.add(cuenta)
    db.commit()
    db.refresh(cuenta)
    return cuenta


@router.delete("/{cuenta_id}")
def eliminar_cuenta(
    cuenta_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = (
        db.query(Cuenta)
        .filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario.id)
        .first()
    )
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    db.delete(cuenta)
    db.commit()
    return {"ok": True}
