"""Lista interna de las formas de asunto que más fallan (contador anónimo y opt-in). Solo para el equipo:
exige el secreto de los crons (X-Cron-Secret). No devuelve nada que identifique a una persona."""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app import formas_asunto
from app.auth import cron_autorizado
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
