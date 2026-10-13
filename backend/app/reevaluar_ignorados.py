"""Recuperar correos de bancos que se descartaron por no leerles el monto.

Antes, un correo sin monto quedaba `ignorado` para siempre y nunca se volvía a leer, aunque el lector
mejorara. Eso hizo perder transacciones reales: Nequi escribe «Recibiste 30.000 de ...» sin el «$» y
el lector no veía el monto. Este paso corre UNA vez por usuario y versión del lector: borra esas filas
(solo las de remitentes bancarios que parecen una notificación de transacción) y reinicia la ventana de
lectura, de modo que la siguiente sincronización las lea de nuevo con el lector corregido. Es seguro
repetirlo: la marca por usuario evita que corra dos veces, y un correo que de verdad no es una
transacción vuelve a quedar `ignorado`."""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.crons import reclamar_marca
from app.extractos_gmail import banco_por_remitente, es_notificacion_transaccion
from app.models import CorreoGasto, SyncGmail

logger = logging.getLogger(__name__)

CLAVE = "reevaluar_ignorados"
VERSION = "v1-monto-sin-signo"  # súbela cuando el lector de montos mejore y valga la pena releer


def candidatos(db: Session, usuario_id: str) -> list[CorreoGasto]:
    """Correos `ignorado` sin monto, de un banco conocido, que parecen una notificación de transacción."""
    filas = (
        db.query(CorreoGasto)
        .filter(CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado == "ignorado")
        .all()
    )
    return [
        f for f in filas
        if (f.monto or 0) <= 0
        and banco_por_remitente(f.remitente or "")
        and es_notificacion_transaccion(f.asunto or "", f.snippet or "")
    ]


def preparar(db: Session, usuario_id: str) -> int:
    """Devuelve cuántos correos se soltaron para releerlos. Nunca lanza: una falla aquí no debe
    impedir la sincronización."""
    try:
        if not reclamar_marca(db, usuario_id, CLAVE, VERSION):
            return 0
        filas = candidatos(db, usuario_id)
        for f in filas:
            db.delete(f)
        if filas:
            sync = db.get(SyncGmail, usuario_id)
            if sync is not None and not sync.en_curso:
                sync.ultima_sync = None  # la próxima corrida usa la ventana larga (respeta el punto de partida)
        db.commit()
        if filas:
            logger.info("Reevaluar ignorados: %s correos de bancos se leerán de nuevo (usuario %s)", len(filas), usuario_id[:8])
        return len(filas)
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Reevaluar ignorados falló (se ignora)")
        return 0
