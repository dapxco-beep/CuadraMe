"""Salud de datos (ver app/salud_datos.py y docs/SALUD_DE_DATOS.md).

GET /salud   los hallazgos de LA PERSONA que pregunta (nunca de otra). Solo lectura."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import salud_autocuracion, salud_datos
from app.auth import UsuarioActual, get_current_user
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
