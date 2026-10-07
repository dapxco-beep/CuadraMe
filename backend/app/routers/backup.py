from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.backup import enviar_backup_por_correo
from app.auth import cron_autorizado
from app.crons import liberar_marca, reclamar_marca
from app.database import get_db
from app.utiles import ahora_co

router = APIRouter(prefix="/backup", tags=["backup"])

_CLAVE_BACKUP = "backup_diario"


@router.post("/cron/enviar")
def cron_enviar_backup(db: Session = Depends(get_db), x_cron_secret: str = Header(default="")):
    """Pensado para llamarse una vez al día desde el mismo cron externo que
    los demás jobs (cron-job.org): exporta toda la base de datos y la manda
    por correo. Existe porque Supabase Free no incluye backups automáticos.
    Idempotente por día (hora Colombia): si ya se envió hoy responde ok con
    enviado=false, sin mandar un segundo correo."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    hoy = ahora_co().strftime("%Y-%m-%d")
    if not reclamar_marca(db, "sistema", _CLAVE_BACKUP, hoy):
        return {"ok": True, "enviado": False, "motivo": "ya se envió hoy", "procesados": 0, "fallidos": 0}

    try:
        resultado = enviar_backup_por_correo()
    except Exception:
        liberar_marca(db, "sistema", _CLAVE_BACKUP)  # que el próximo intento del día sí pueda enviarlo
        raise
    if not resultado["ok"]:
        liberar_marca(db, "sistema", _CLAVE_BACKUP)
        raise HTTPException(status_code=500, detail=resultado.get("error", "No se pudo enviar el backup"))
    return {**resultado, "enviado": True, "procesados": 1, "fallidos": 0}
