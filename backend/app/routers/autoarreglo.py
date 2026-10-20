"""Autoarreglo (app/autoarreglo.py): la app ordena sola las cuentas de la persona, y se puede ver y deshacer.

  POST /autoarreglo/correr                  un tramo acotado del orden automático (la PWA lo llama al abrir, sin bloquear)
  GET  /autoarreglo/lotes                   lo hecho por lote: cuántos cambios, saldos antes y después por cuenta
  POST /autoarreglo/lotes/{lote}/deshacer   revierte el lote completo (409 si algo posterior lo hizo inconsistente)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import autoarreglo
from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.limites import verificar_limite

router = APIRouter(prefix="/autoarreglo", tags=["autoarreglo"])


@router.post("/correr")
def correr(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Un tramo del orden automático. Respuesta rápida: `{estado: 'trabajando'|'listo', progreso: {hecho, total}, resumen,
    decisiones, cuadre}`. Con 'trabajando' la app vuelve a llamar. Nunca falla: si algo sale mal responde 'listo'."""
    verificar_limite(f"autoarreglo:{usuario.id}", autoarreglo.LIMITE_LLAMADAS_HORA, 3600,
                     "Ordené tus cuentas muchas veces seguidas. Podrás seguir en {espera}.")
    return autoarreglo.correr(db, usuario.id, usuario=usuario, respetar_intervalo=True)


@router.get("/lotes")
def lotes(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Lo que se ordenó solo, lote por lote (el más reciente primero)."""
    return {"lotes": autoarreglo.lotes(db, usuario.id)}


@router.post("/lotes/{lote}/deshacer")
def deshacer(lote: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Deshace el lote completo, en orden inverso. Idempotente."""
    return autoarreglo.deshacer_lote(db, usuario.id, lote)
