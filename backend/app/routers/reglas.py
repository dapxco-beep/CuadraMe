from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.models import ReglaCategoria
from app.schemas import ReglaCategoriaCreate, ReglaCategoriaOut

router = APIRouter(prefix="/reglas-categoria", tags=["reglas"])


@router.get("", response_model=list[ReglaCategoriaOut])
def listar_reglas(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    return (
        db.query(ReglaCategoria)
        .filter(ReglaCategoria.usuario_id == usuario.id)
        .order_by(ReglaCategoria.prioridad.desc())
        .all()
    )


@router.post("", response_model=ReglaCategoriaOut)
def crear_regla(
    data: ReglaCategoriaCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    regla = ReglaCategoria(usuario_id=usuario.id, **data.model_dump())
    db.add(regla)
    db.commit()
    db.refresh(regla)
    return regla


@router.delete("/{regla_id}")
def eliminar_regla(
    regla_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    regla = (
        db.query(ReglaCategoria)
        .filter(ReglaCategoria.id == regla_id, ReglaCategoria.usuario_id == usuario.id)
        .first()
    )
    if not regla:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    db.delete(regla)
    db.commit()
    return {"ok": True}
