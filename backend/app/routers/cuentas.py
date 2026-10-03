from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuentas_ids_accesibles
from app.database import get_db
from app.models import Cuenta, Movimiento
from app.schemas import CuentaCreate, CuentaOut, CuentaUpdate
from app.tarjetas import calc_tarjeta

router = APIRouter(prefix="/cuentas", tags=["cuentas"])


def _serializar(cuenta: Cuenta) -> dict:
    """Cuenta + (si es tarjeta de crédito) los cálculos de cupo y fechas."""
    return {
        "id": cuenta.id,
        "nombre": cuenta.nombre,
        "tipo": cuenta.tipo,
        "saldo": cuenta.saldo,
        "moneda": cuenta.moneda,
        "icono": cuenta.icono,
        "cupo_total": cuenta.cupo_total,
        "dia_corte": cuenta.dia_corte,
        "dia_pago": cuenta.dia_pago,
        "tasa_ea": cuenta.tasa_ea,
        "tarjeta": calc_tarjeta(cuenta) if cuenta.tipo == "credito" else None,
    }


@router.get("", response_model=list[CuentaOut])
def listar_cuentas(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    ids = cuentas_ids_accesibles(db, usuario.id)
    return [_serializar(c) for c in db.query(Cuenta).filter(Cuenta.id.in_(ids)).all()]


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
    return _serializar(cuenta)


@router.put("/{cuenta_id}", response_model=CuentaOut)
def editar_cuenta(
    cuenta_id: str,
    data: CuentaUpdate,
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

    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(cuenta, campo, valor)

    db.commit()
    db.refresh(cuenta)
    return _serializar(cuenta)


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

    tiene_movimientos = (
        db.query(Movimiento.id).filter(Movimiento.cuenta_id == cuenta_id).first()
        is not None
    )
    if tiene_movimientos:
        raise HTTPException(
            status_code=400,
            detail="Esta cuenta tiene movimientos registrados y no se puede eliminar. Puedes dejarla en $0 en vez de borrarla.",
        )

    db.delete(cuenta)
    db.commit()
    return {"ok": True}
