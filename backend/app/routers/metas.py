from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.finanzas import calc_progreso_meta
from app.models import Meta
from app.schemas import MetaCreate, MetaOut, MetaUpdate

router = APIRouter(prefix="/metas", tags=["metas"])


def _serializar(meta: Meta) -> dict:
    return {
        "id": meta.id,
        "nombre": meta.nombre,
        "descripcion": meta.descripcion,
        "monto_objetivo": meta.monto_objetivo,
        "monto_actual": meta.monto_actual,
        "fecha_inicio": meta.fecha_inicio,
        "fecha_objetivo": meta.fecha_objetivo,
        "activa": meta.activa,
        **calc_progreso_meta(meta),
    }


@router.get("", response_model=list[MetaOut])
def listar_metas(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    metas = (
        db.query(Meta)
        .filter(Meta.usuario_id == usuario.id, Meta.activa.is_(True))
        .all()
    )
    return [_serializar(m) for m in metas]


@router.post("", response_model=MetaOut)
def crear_meta(
    data: MetaCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    meta = Meta(usuario_id=usuario.id, **data.model_dump())
    db.add(meta)
    db.commit()
    db.refresh(meta)
    return _serializar(meta)


@router.patch("/{meta_id}", response_model=MetaOut)
def actualizar_meta(
    meta_id: str,
    data: MetaUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    meta = db.query(Meta).filter(Meta.id == meta_id, Meta.usuario_id == usuario.id).first()
    if not meta:
        raise HTTPException(status_code=404, detail="Meta no encontrada")

    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(meta, campo, valor)
    db.commit()
    db.refresh(meta)
    return _serializar(meta)


@router.post("/{meta_id}/aportar", response_model=MetaOut)
def aportar_meta(
    meta_id: str,
    monto: float,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    meta = db.query(Meta).filter(Meta.id == meta_id, Meta.usuario_id == usuario.id).first()
    if not meta:
        raise HTTPException(status_code=404, detail="Meta no encontrada")

    meta.monto_actual = (meta.monto_actual or 0) + monto
    db.commit()
    db.refresh(meta)
    return _serializar(meta)


@router.delete("/{meta_id}")
def eliminar_meta(
    meta_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    meta = db.query(Meta).filter(Meta.id == meta_id, Meta.usuario_id == usuario.id).first()
    if not meta:
        raise HTTPException(status_code=404, detail="Meta no encontrada")
    meta.activa = False
    db.commit()
    return {"ok": True}
