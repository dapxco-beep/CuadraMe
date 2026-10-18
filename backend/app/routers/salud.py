"""Salud de datos (ver app/salud_datos.py y docs/SALUD_DE_DATOS.md).

GET /salud   los hallazgos de LA PERSONA que pregunta (nunca de otra). Solo lectura."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import salud_autocuracion, salud_datos, salud_monitor
from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.database import get_db

router = APIRouter(prefix="/salud", tags=["salud"])


@router.get("")
def hallazgos(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    lista = salud_datos.diagnosticar(db, usuario.id)
    return {"total": len(lista), "hallazgos": lista}


class CrearTarjeta(BaseModel):
    banco: str = Field(min_length=1, max_length=60)


@router.post("/crear-tarjeta")
def crear_tarjeta(data: CrearTarjeta, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """«Crear tu cuenta de tarjeta <Banco>»: un toque. Crea la cuenta (crédito, saldo 0) y pasa a ella los
    extractos de tarjeta de ese banco que aún no se importaron. No importa movimientos ni toca saldos."""
    r = salud_autocuracion.crear_cuenta_tarjeta(db, usuario.id, data.banco)
    if r is None:
        raise HTTPException(status_code=404, detail="No encontramos extractos de tarjeta de ese banco.")
    return {"ok": True, **r}


@router.post("/cron/resumen")
def cron_resumen(x_cron_secret: str = Header(default=""), db: Session = Depends(get_db)):
    """Monitor para el dueño (cron diario ~7:30 Colombia, header X-Cron-Secret). Devuelve SOLO contadores
    agregados y anónimos y, si alguno supera su umbral, deja UN aviso por día en «Actividad reciente»
    (push + correo al administrador). Idempotente por día. Ver docs/SALUD_DE_DATOS.md."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    return {**salud_monitor.revisar(db), "procesados": 1, "fallidos": 0}
