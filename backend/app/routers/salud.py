"""Salud de datos (ver app/salud_datos.py y docs/SALUD_DE_DATOS.md).

GET /salud   los hallazgos de LA PERSONA que pregunta (nunca de otra). Solo lectura."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import salud_datos
from app.auth import UsuarioActual, get_current_user
from app.database import get_db

router = APIRouter(prefix="/salud", tags=["salud"])


@router.get("")
def hallazgos(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    lista = salud_datos.diagnosticar(db, usuario.id)
    return {"total": len(lista), "hallazgos": lista}
