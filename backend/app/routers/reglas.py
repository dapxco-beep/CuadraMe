from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.autocat import aplicar_a_anteriores, guardar_regla_aprendida
from app.models import Categoria, ReglaCategoria
from app.schemas import AprenderReglaRequest, ReglaCategoriaCreate, ReglaCategoriaOut

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


@router.post("/aprender")
def aprender_regla(
    data: AprenderReglaRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Guarda la regla del comercio de esta descripción (una por huella: si ya existe se
    actualiza) y, si se pide, recategoriza los movimientos anteriores de ese comercio."""
    categoria = data.categoria.strip()
    hay_lista = db.query(Categoria.id).filter(Categoria.usuario_id == usuario.id).first()
    if hay_lista and not db.query(Categoria.id).filter(
        Categoria.usuario_id == usuario.id, Categoria.nombre == categoria
    ).first():
        raise HTTPException(status_code=400, detail="Esa categoría no existe en tu lista")
    r = guardar_regla_aprendida(
        db, usuario.id, data.descripcion, categoria, tipo=data.tipo, confirmar_peligrosa=data.confirmar_peligrosa
    )
    anteriores = 0
    if r["guardada"] and data.aplicar_anteriores:
        anteriores = aplicar_a_anteriores(db, usuario.id, r["huella"], categoria)
    db.commit()
    return {**r, "anteriores_actualizados": anteriores}


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
