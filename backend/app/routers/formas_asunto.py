"""Lista interna de las formas de asunto que más fallan (contador anónimo y opt-in). Solo para el equipo:
exige el secreto de los crons (X-Cron-Secret). No devuelve nada que identifique a una persona."""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import formas_asunto
from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.database import get_db

router = APIRouter(prefix="/formas-asunto", tags=["formas-asunto"])


@router.get("/cron/mas-frecuentes")
def mas_frecuentes(
    limite: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    x_cron_secret: str = Header(default=""),
):
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    return formas_asunto.mas_frecuentes(db, limite)


class PantallaAbierta(BaseModel):
    ruta: str = Field(max_length=90)


@router.post("/pantalla")
def anotar_pantalla(
    datos: PantallaAbierta,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """La app avisa que se abrió una pantalla. Solo cuenta si la persona aceptó las estadísticas anónimas; si no, no hace
    nada (200 sin efecto). Nunca falla la app por esto."""
    anotada = formas_asunto.registrar_pantalla(db, usuario.id, datos.ruta)
    if anotada:
        db.commit()
    return {"ok": True}


@router.get("/cron/pantallas")
def pantallas(
    limite: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
    x_cron_secret: str = Header(default=""),
):
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    return formas_asunto.pantallas_mas_usadas(db, limite)
