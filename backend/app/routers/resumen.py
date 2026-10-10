"""Resumen semanal por correo.

- GET/PUT /resumen/preferencias: opt-in del usuario (apagado por defecto).
- POST /resumen/cron/semanal (header X-Cron-Secret): manda el resumen a quien lo activó.
  Idempotente por usuario y semana ISO (tabla marcas_cron) y tolerante a fallos por usuario.
Este archivo NO crea el cron en cron-job.org; cómo programarlo está en docs/SALIDA_A_PRODUCCION.md."""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import resumen_semanal as rs
from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.crons import Corrida, liberar_marca, reclamar_marca
from app.database import get_db
from app.models_fiscal import AjusteUsuario
from app.utiles import ahora_co

router = APIRouter(prefix="/resumen", tags=["resumen"])
logger = logging.getLogger(__name__)

CLAVE_MARCA = "resumen_correo_semanal"


class PreferenciasResumen(BaseModel):
    correo: bool | None = None          # resumen semanal por correo
    ocultar_montos: bool | None = None  # «ocultar saldos»: los push semanales salen sin montos


@router.get("/preferencias")
def obtener_preferencias(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    aj = db.query(AjusteUsuario).filter(AjusteUsuario.usuario_id == usuario.id).first()
    return {"correo": bool(aj and aj.resumen_correo), "email": usuario.email,
            "ocultar_montos": bool(aj and aj.ocultar_montos)}


@router.put("/preferencias")
def guardar_preferencias(
    data: PreferenciasResumen,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Opt-in explícito. Se guarda el correo actual al activar (el cron no tiene la sesión) y se borra al apagar."""
    aj = db.query(AjusteUsuario).filter(AjusteUsuario.usuario_id == usuario.id).first()
    if not aj:
        aj = AjusteUsuario(usuario_id=usuario.id)
        db.add(aj)
    if data.correo is not None:
        aj.resumen_correo = data.correo
        aj.email_resumen = usuario.email if data.correo else None
    if data.ocultar_montos is not None:
        aj.ocultar_montos = data.ocultar_montos
    db.commit()
    return {"ok": True, "correo": bool(aj.resumen_correo), "ocultar_montos": bool(aj.ocultar_montos)}


def _enviar_a(db: Session, aj: AjusteUsuario, hoy, semana: str) -> str:
    """Trabajo de UN usuario. Devuelve 'enviado', 'ya_enviado' o 'sin_datos'."""
    datos = rs.datos_semana(db, aj.usuario_id, hoy)
    if datos["vacio"]:
        return "sin_datos"
    # Se reclama la marca ANTES de enviar: dos ejecuciones a la vez dejan pasar solo a una.
    if not reclamar_marca(db, aj.usuario_id, CLAVE_MARCA, semana):
        return "ya_enviado"
    try:
        ok = rs.enviar_correo(aj.email_resumen, rs.asunto(datos), rs.html_correo(datos), rs.texto_plano(datos))
    except Exception:
        liberar_marca(db, aj.usuario_id, CLAVE_MARCA)  # que la próxima corrida lo reintente
        raise
    if not ok:  # Resend sin configurar
        liberar_marca(db, aj.usuario_id, CLAVE_MARCA)
        return "sin_datos"
    return "enviado"


@router.post("/cron/semanal")
def cron_semanal(db: Session = Depends(get_db), x_cron_secret: str = Header(default="")):
    """Una vez por semana (domingo en la tarde). Un fallo con un usuario no frena a los demás."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    hoy = ahora_co()
    iso = hoy.isocalendar()
    semana = f"{iso[0]}-W{iso[1]:02d}"
    destinatarios = (
        db.query(AjusteUsuario)
        .filter(AjusteUsuario.resumen_correo == True, AjusteUsuario.email_resumen.isnot(None))  # noqa: E712
        .all()
    )
    ids = [a.usuario_id for a in destinatarios]  # los ORM se invalidan con un rollback: se guardan los ids
    res = {"ok": True, "semana": semana, "enviados": 0, "ya_enviados": 0, "sin_datos": 0}
    corrida = Corrida(db)
    for uid in ids:
        with corrida.aislar(uid):
            aj = db.query(AjusteUsuario).filter(AjusteUsuario.usuario_id == uid).first()
            if not aj or not aj.resumen_correo or not aj.email_resumen:
                continue
            r = _enviar_a(db, aj, hoy, semana)
            res[{"enviado": "enviados", "ya_enviado": "ya_enviados", "sin_datos": "sin_datos"}[r]] += 1
    return {**res, **corrida.resumen()}
