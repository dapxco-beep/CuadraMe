from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import bloquear_cuenta, cuenta_accesible, puede_editar_cuenta
from app.database import get_db
from app.finanzas import calc_progreso_meta
from app.models import Meta
from app.rachas import otorgar_vida_si_nueva
from app.schemas import MetaCreate, MetaOut, MetaUpdate

router = APIRouter(prefix="/metas", tags=["metas"])


def _validar_cuenta_origen(db: Session, usuario_id: str, cuenta_id: str | None) -> None:
    """La cuenta de la que salen los aportes automáticos debe ser del propio
    usuario: si no, bastaría conocer el id de una cuenta ajena para que el cron
    descontara plata de ella."""
    if not cuenta_id:
        return
    cuenta = cuenta_accesible(db, usuario_id, cuenta_id)
    if not cuenta or cuenta.usuario_id != usuario_id:
        raise HTTPException(status_code=404, detail="Cuenta de origen no encontrada")


def _serializar(meta: Meta) -> dict:
    return {
        "id": meta.id,
        "nombre": meta.nombre,
        "descripcion": meta.descripcion,
        "monto_objetivo": meta.monto_objetivo,
        "monto_actual": meta.monto_actual,
        "icono": meta.icono,
        "fecha_inicio": meta.fecha_inicio,
        "fecha_objetivo": meta.fecha_objetivo,
        "aporte_automatico": meta.aporte_automatico,
        "dia_aporte": meta.dia_aporte,
        "cuenta_origen_id": meta.cuenta_origen_id,
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
    _validar_cuenta_origen(db, usuario.id, data.cuenta_origen_id)
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

    cambios = data.model_dump(exclude_unset=True)
    _validar_cuenta_origen(db, usuario.id, cambios.get("cuenta_origen_id"))
    for campo, valor in cambios.items():
        setattr(meta, campo, valor)
    db.commit()
    db.refresh(meta)
    return _serializar(meta)


@router.post("/{meta_id}/aportar", response_model=MetaOut)
def aportar_meta(
    meta_id: str,
    monto: float,
    cuenta_id: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    if monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a cero")

    # Se bloquea la fila de la meta (y de la cuenta) hasta el commit: dos aportes
    # simultáneos ya no leen el mismo monto_actual y se pisan uno al otro.
    meta = (
        db.query(Meta)
        .filter(Meta.id == meta_id, Meta.usuario_id == usuario.id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not meta:
        raise HTTPException(status_code=404, detail="Meta no encontrada")

    if cuenta_id:
        cuenta = cuenta_accesible(db, usuario.id, cuenta_id)
        if not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta):
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        cuenta = bloquear_cuenta(db, cuenta.id)
        if cuenta.saldo < monto:
            raise HTTPException(status_code=400, detail="Saldo insuficiente en la cuenta de origen")
        cuenta.saldo -= monto

    ya_estaba_completada = (meta.monto_actual or 0) >= meta.monto_objetivo
    meta.monto_actual = (meta.monto_actual or 0) + monto
    db.commit()
    db.refresh(meta)

    if not ya_estaba_completada and meta.monto_actual >= meta.monto_objetivo:
        otorgar_vida_si_nueva(db, usuario.id, f"meta_cumplida_{meta.id}")

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
