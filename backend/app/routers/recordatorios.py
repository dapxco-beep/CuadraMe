"""GET /recordatorios: tarjetas del Inicio (vencimiento de tarjeta, presupuesto al 80 %, extractos
por revisar). Solo calcula; descartarlos se guarda en el dispositivo (cada recordatorio trae una
`clave` que cambia cuando hay una situación nueva)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import recordatorios as rec
from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.utiles import ahora_co

router = APIRouter(prefix="/recordatorios", tags=["recordatorios"])


@router.get("")
def listar(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    return rec.calcular(db, usuario.id, ahora_co())
