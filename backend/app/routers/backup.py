from fastapi import APIRouter, Header, HTTPException

from app.backup import enviar_backup_por_correo
from app.auth import cron_autorizado

router = APIRouter(prefix="/backup", tags=["backup"])


@router.post("/cron/enviar")
def cron_enviar_backup(x_cron_secret: str = Header(default="")):
    """Pensado para llamarse una vez al día desde el mismo cron externo que
    los demás jobs (cron-job.org): exporta toda la base de datos y la manda
    por correo. Existe porque Supabase Free no incluye backups automáticos."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    resultado = enviar_backup_por_correo()
    if not resultado["ok"]:
        raise HTTPException(status_code=500, detail=resultado.get("error", "No se pudo enviar el backup"))
    return resultado
