import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.derechos_titular import armar_json, armar_zip, borrar_todo, recopilar
from app.limites import verificar_limite
from app.models import Perfil
from app.claves_api import asignar_clave_nueva, tiene_clave
from app.utiles import ahora_co
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
    return perfil


@router.get("/api-key")
def obtener_api_key(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    if not tiene_clave(db, perfil):
        # Primera vez: se crea y se muestra completa (única ocasión, junto con regenerar).
        return {"api_key": asignar_clave_nueva(db, perfil), "tiene_clave": True, "nueva": True}
    if perfil.api_key:
        # Clave antigua aún en claro (se migra a hash la primera vez que el Atajo la use).
        return {"api_key": perfil.api_key, "tiene_clave": True, "nueva": False}
    # Ya guardada como hash: no se puede mostrar. Solo el prefijo para reconocerla.
    return {"api_key": None, "tiene_clave": True, "nueva": False, "prefijo": perfil.api_key_prefijo,
            "mensaje": "Por seguridad tu clave ya no se puede mostrar. Si la perdiste, genera una nueva."}


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
    clave = asignar_clave_nueva(db, perfil)  # también reinicia api_key_ultimo_uso
    return {"api_key": clave, "tiene_clave": True, "nueva": True}


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


class AutoimportarExtractosUpdate(BaseModel):
    activo: bool


@router.get("/autoimportar-extractos")
def obtener_autoimportar_extractos(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    return {"activo": bool(perfil.autoimportar_extractos), "confianza_autoimport": perfil.confianza_autoimport or 0.75}


@router.put("/autoimportar-extractos")
def actualizar_autoimportar_extractos(
    data: AutoimportarExtractosUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Opcional y apagado por defecto: al subir un extracto, importa solo lo que la app
    reconoce con certeza (umbral = confianza-autoimport). Lo importado se puede deshacer."""
    perfil = _get_or_create_perfil(db, usuario.id)
    perfil.autoimportar_extractos = data.activo
    db.commit()
    return {"activo": bool(perfil.autoimportar_extractos)}




@router.get("/mis-datos")
def descargar_mis_datos(
    formato: Literal["zip", "json"] = "zip",
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Derecho de acceso y portabilidad (Ley 1581 de 2012): todo lo que CuadraMe guarda
    del usuario. ZIP con un JSON completo + un CSV por tabla (abren en Excel), o solo el
    JSON con ?formato=json. Se limita a 5 por hora: armar el archivo recorre todas las tablas."""
    verificar_limite(f"mis-datos:{usuario.id}", 5, 3600, "Ya descargaste tus datos varias veces. Intenta de nuevo en {espera}.")
    datos = recopilar(db, usuario.id, usuario.email)
    hoy = ahora_co().strftime("%Y-%m-%d")
    if formato == "json":
        return Response(
            content=armar_json(datos, usuario.email), media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=cuadrame_mis_datos_{hoy}.json"},
        )
    return Response(
        content=armar_zip(datos, usuario.email), media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=cuadrame_mis_datos_{hoy}.zip"},
    )


@router.post("/eliminar-cuenta")
def eliminar_cuenta(
    data: EliminarCuentaRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Derecho de supresión (Ley 1581 de 2012): borra TODOS los datos del usuario.
    Es irreversible. Se exige la palabra ELIMINAR para evitar llamadas accidentales.
    Solo actúa sobre la sesión de quien llama: nadie puede borrar la cuenta de otro.
    La lógica vive en app/derechos_titular.py (también revoca el permiso de Gmail)."""
    if data.confirmacion.strip().upper() != "ELIMINAR":
        raise HTTPException(status_code=400, detail='Para confirmar, envía confirmacion="ELIMINAR"')

    resultado = borrar_todo(db, usuario.id, usuario.email)
    respuesta = {"ok": True, "auth_eliminado": resultado["auth_eliminado"],
                 "gmail_revocado": resultado["gmail_revocado"]}
    if resultado["aviso"]:
        respuesta["aviso"] = resultado["aviso"]
    return respuesta
