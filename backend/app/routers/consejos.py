"""GET /consejos: consejos personalizados (reglas puras, sin IA externa) para el Inicio.
Solo calcula con los datos del propio usuario; descartarlos se guarda en el dispositivo
(cada consejo trae un `id` estable que incluye el periodo o la situación)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import consejos as motor
from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.utiles import ahora_co

router = APIRouter(prefix="/consejos", tags=["consejos"])


@router.get("")
def listar(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    return motor.consejos_de_usuario(db, usuario.id, ahora_co())
