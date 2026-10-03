from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import puede_editar_cuenta
from app.database import get_db
from app.models import Cuenta, CuentaCompartida, InvitacionCuenta
from app.schemas import CuentaCompartidaOut, InvitacionOut, InvitarRequest

router = APIRouter(prefix="/cuentas", tags=["compartir"])


@router.post("/{cuenta_id}/invitar", response_model=InvitacionOut)
def invitar(
    cuenta_id: str,
    data: InvitarRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = db.query(Cuenta).filter(Cuenta.id == cuenta_id).first()
    if not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    if cuenta.usuario_id != usuario.id:
        raise HTTPException(status_code=403, detail="Solo el dueño de la cuenta puede invitar")

    email_invitado = data.email.strip().lower()
    if usuario.email and email_invitado == usuario.email.lower():
        raise HTTPException(status_code=400, detail="No puedes invitarte a ti mismo")

    # Evita invitaciones duplicadas: si ya hay una pendiente para este email
    # en esta cuenta, no crear otra fila (el usuario invitado vería la misma
    # invitación repetida en su lista de pendientes).
    ya_pendiente = (
        db.query(InvitacionCuenta)
        .filter(
            InvitacionCuenta.cuenta_id == cuenta_id,
            InvitacionCuenta.email_invitado == email_invitado,
            InvitacionCuenta.estado == "pendiente",
        )
        .first()
    )
    if ya_pendiente:
        raise HTTPException(status_code=400, detail="Ya existe una invitación pendiente para este email")

    invitacion = InvitacionCuenta(
        cuenta_id=cuenta_id,
        invitado_por=usuario.id,
        email_invitado=email_invitado,
        rol=data.rol if data.rol in ("viewer", "editor") else "viewer",
    )
    db.add(invitacion)
    db.commit()
    db.refresh(invitacion)
    return invitacion


@router.get("/{cuenta_id}/invitaciones", response_model=list[InvitacionOut])
def listar_invitaciones(
    cuenta_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = db.query(Cuenta).filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario.id).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return db.query(InvitacionCuenta).filter(InvitacionCuenta.cuenta_id == cuenta_id).all()


@router.get("/{cuenta_id}/compartida-con", response_model=list[CuentaCompartidaOut])
def listar_compartida_con(
    cuenta_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = db.query(Cuenta).filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario.id).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return db.query(CuentaCompartida).filter(CuentaCompartida.cuenta_id == cuenta_id).all()


@router.get("/invitaciones/pendientes", response_model=list[InvitacionOut])
def mis_invitaciones_pendientes(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Invitaciones que llegaron al email del usuario actual, aún sin aceptar/rechazar."""
    if not usuario.email:
        return []
    return (
        db.query(InvitacionCuenta)
        .filter(
            InvitacionCuenta.email_invitado == usuario.email.lower(),
            InvitacionCuenta.estado == "pendiente",
        )
        .all()
    )


@router.post("/invitaciones/{invitacion_id}/aceptar")
def aceptar_invitacion(
    invitacion_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    invitacion = (
        db.query(InvitacionCuenta)
        .filter(InvitacionCuenta.id == invitacion_id, InvitacionCuenta.estado == "pendiente")
        .first()
    )
    if not invitacion or invitacion.email_invitado != (usuario.email or "").lower():
        raise HTTPException(status_code=404, detail="Invitación no encontrada")

    ya_compartida = (
        db.query(CuentaCompartida)
        .filter(CuentaCompartida.cuenta_id == invitacion.cuenta_id, CuentaCompartida.usuario_id == usuario.id)
        .first()
    )
    if not ya_compartida:
        db.add(
            CuentaCompartida(
                cuenta_id=invitacion.cuenta_id,
                usuario_id=usuario.id,
                rol=invitacion.rol,
            )
        )

    invitacion.estado = "aceptada"
    db.commit()
    return {"ok": True}


@router.post("/invitaciones/{invitacion_id}/rechazar")
def rechazar_invitacion(
    invitacion_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    invitacion = (
        db.query(InvitacionCuenta)
        .filter(InvitacionCuenta.id == invitacion_id, InvitacionCuenta.estado == "pendiente")
        .first()
    )
    if not invitacion or invitacion.email_invitado != (usuario.email or "").lower():
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    invitacion.estado = "rechazada"
    db.commit()
    return {"ok": True}


@router.delete("/{cuenta_id}/compartir/{usuario_compartido_id}")
def revocar_acceso(
    cuenta_id: str,
    usuario_compartido_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = db.query(Cuenta).filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario.id).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    db.query(CuentaCompartida).filter(
        CuentaCompartida.cuenta_id == cuenta_id, CuentaCompartida.usuario_id == usuario_compartido_id
    ).delete()
    db.commit()
    return {"ok": True}
