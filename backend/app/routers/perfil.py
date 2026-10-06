import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.config import settings
from app.database import Base, get_db
from app.models import Cuenta, CuentaCompartida, HistorialExtracto, InvitacionCuenta, Movimiento, Perfil, gen_api_key
from app.models_gastos import GastoCompartido, GrupoGasto, MiembroGrupoGasto, ParteGasto
from app.schemas import ConfianzaAutoimportUpdate, EliminarCuentaRequest

router = APIRouter(prefix="/perfil", tags=["perfil"])
logger = logging.getLogger(__name__)


def _get_or_create_perfil(db: Session, usuario_id: str) -> Perfil:
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
    if not perfil:
        perfil = Perfil(usuario_id=usuario_id, plan="free")
        db.add(perfil)
        db.commit()
        db.refresh(perfil)
    if not perfil.api_key:
        perfil.api_key = gen_api_key()
        db.commit()
        db.refresh(perfil)
    return perfil


@router.get("/api-key")
def obtener_api_key(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    return {"api_key": perfil.api_key}


class RecordatorioUpdate(BaseModel):
    activo: bool


@router.get("/recordatorio-diario")
def obtener_recordatorio_diario(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    return {"activo": bool(perfil.recordatorio_diario)}


@router.put("/recordatorio-diario")
def actualizar_recordatorio_diario(
    data: RecordatorioUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Activa o apaga el aviso de las 8pm 'hoy no has registrado nada'."""
    perfil = _get_or_create_perfil(db, usuario.id)
    perfil.recordatorio_diario = data.activo
    db.commit()
    return {"activo": bool(perfil.recordatorio_diario)}


@router.post("/api-key/regenerar")
def regenerar_api_key(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    perfil.api_key = gen_api_key()
    perfil.api_key_ultimo_uso = None  # la clave nueva aún no se ha usado
    db.commit()
    return {"api_key": perfil.api_key}


@router.get("/confianza-autoimport")
def obtener_confianza_autoimport(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    return {"confianza_autoimport": perfil.confianza_autoimport or 0.75}


@router.put("/confianza-autoimport")
def actualizar_confianza_autoimport(
    data: ConfianzaAutoimportUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    if not (0.5 <= data.confianza_autoimport <= 0.95):
        raise HTTPException(status_code=400, detail="El valor debe estar entre 0.5 y 0.95")
    perfil = _get_or_create_perfil(db, usuario.id)
    perfil.confianza_autoimport = data.confianza_autoimport
    db.commit()
    return {"confianza_autoimport": perfil.confianza_autoimport}


@router.post("/eliminar-cuenta")
def eliminar_cuenta(
    data: EliminarCuentaRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Derecho de supresión (Ley 1581 de 2012): borra TODOS los datos del usuario.
    Es irreversible. Se exige la palabra ELIMINAR para evitar llamadas accidentales."""
    if data.confirmacion.strip().upper() != "ELIMINAR":
        raise HTTPException(status_code=400, detail='Para confirmar, envía confirmacion="ELIMINAR"')

    uid = usuario.id
    mis_cuentas = [c.id for c in db.query(Cuenta.id).filter(Cuenta.usuario_id == uid).all()]

    # 1) Movimientos que yo registré en cuentas AJENAS (compartidas conmigo): se
    #    devuelve su efecto al saldo del dueño antes de borrarlos, para no dejarle
    #    el saldo descuadrado.
    from app.routers.movimientos import _delta_saldo

    ajenos = (
        db.query(Movimiento)
        .filter(Movimiento.usuario_id == uid, Movimiento.cuenta_id.notin_(mis_cuentas or [""]))
        .all()
    )
    for m in ajenos:
        cuenta = db.query(Cuenta).filter(Cuenta.id == m.cuenta_id).first()
        if cuenta:
            cuenta.saldo -= _delta_saldo(m.tipo, m.monto)

    # 2) Todo lo que cuelga de mis cuentas, sin importar quién lo escribió.
    if mis_cuentas:
        db.query(Movimiento).filter(Movimiento.cuenta_id.in_(mis_cuentas)).delete(synchronize_session=False)
        db.query(HistorialExtracto).filter(HistorialExtracto.cuenta_id.in_(mis_cuentas)).delete(synchronize_session=False)
        db.query(CuentaCompartida).filter(CuentaCompartida.cuenta_id.in_(mis_cuentas)).delete(synchronize_session=False)
        db.query(InvitacionCuenta).filter(InvitacionCuenta.cuenta_id.in_(mis_cuentas)).delete(synchronize_session=False)

    # 3) Invitaciones que hice o recibí.
    db.query(InvitacionCuenta).filter(InvitacionCuenta.invitado_por == uid).delete(synchronize_session=False)
    if usuario.email:
        db.query(InvitacionCuenta).filter(
            InvitacionCuenta.email_invitado == usuario.email.lower()
        ).delete(synchronize_session=False)

    # 4) Tablas hijas SIN usuario_id: cuelgan de grupos y gastos compartidos del
    #    usuario y quedarían huérfanas (con nombres/montos de terceros) si solo se
    #    borrara por usuario_id. Se borran por sus padres, antes que ellos.
    mis_grupos = db.query(GrupoGasto.id).filter(GrupoGasto.usuario_id == uid)
    mis_gastos = db.query(GastoCompartido.id).filter(GastoCompartido.usuario_id == uid)
    db.query(MiembroGrupoGasto).filter(MiembroGrupoGasto.grupo_id.in_(mis_grupos)).delete(synchronize_session=False)
    db.query(ParteGasto).filter(ParteGasto.gasto_id.in_(mis_gastos)).delete(synchronize_session=False)

    # 5) Cualquier tabla con columna usuario_id (perfil, cuentas, presupuestos, metas,
    #    deudas, rachas, push...). Recorrer el metadata evita olvidar una tabla nueva.
    for tabla in Base.metadata.sorted_tables:
        if "usuario_id" in tabla.c:
            db.execute(tabla.delete().where(tabla.c.usuario_id == uid))
    db.commit()

    auth_eliminado = False
    aviso = None
    if settings.supabase_service_role_key:
        try:
            resp = httpx.delete(
                f"{settings.supabase_url}/auth/v1/admin/users/{uid}",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                },
                timeout=15,
            )
            auth_eliminado = resp.status_code in (200, 204)
            if not auth_eliminado:
                logger.error("Supabase Auth respondió %s al borrar el usuario %s", resp.status_code, uid)
        except httpx.HTTPError:
            logger.exception("No se pudo borrar el usuario %s de Supabase Auth", uid)
        if not auth_eliminado:
            # Los datos ya se borraron (commit arriba): no se pierde ese avance.
            aviso = "Tus datos se borraron, pero no pudimos cerrar tu acceso; escríbenos a soporte"

    respuesta = {"ok": True, "auth_eliminado": auth_eliminado}
    if aviso:
        respuesta["aviso"] = aviso
    return respuesta
