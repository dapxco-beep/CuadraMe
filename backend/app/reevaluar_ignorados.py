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
from app.extractos_gmail import banco_por_remitente, es_aviso_no_transaccion, es_notificacion_transaccion
from app.gmail_extract import extraer_monto
from app.models import CorreoGasto, SyncGmail

logger = logging.getLogger(__name__)

CLAVE = "reevaluar_ignorados"
VERSION = "v3-sin-nit-ni-documentos"  # súbela cuando el lector de montos mejore y valga la pena releer


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


def avisos_pendientes(db: Session, usuario_id: str) -> list[CorreoGasto]:
    """Correos que quedaron «pendiente» pero en realidad son avisos (extracto listo, tarjeta agregada, pago
    fallido...): entraron cuando el lector aún no distinguía esos avisos o leía números de cuenta como monto."""
    filas = db.query(CorreoGasto).filter(CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado == "pendiente").all()
    return [f for f in filas if es_aviso_no_transaccion(f.asunto or "", f.snippet or "")]


def corregir_montos_de_documentos(db: Session, usuario_id: str) -> int:
    """Pendientes cuyo monto era en realidad un NIT, número de cuenta o teléfono. Solo toca los que el lector
    viejo leía así (mismo monto sin sanear) y el nuevo lee distinto: con otro monto lo corrige; sin monto
    los pasa a «ignorado» (no se borran, para que no resuciten)."""
    n = 0
    filas = db.query(CorreoGasto).filter(CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado == "pendiente").all()
    for f in filas:
        texto = f"{f.asunto or ''} {f.snippet or ''}"
        viejo = extraer_monto(texto, sanear=False)
        nuevo = extraer_monto(texto)
        if viejo and abs(viejo - (f.monto or 0)) < 0.01 and abs(nuevo - viejo) >= 0.01:
            if nuevo > 0:
                f.monto = nuevo
            else:
                f.estado = "ignorado"
            n += 1
    return n


def preparar(db: Session, usuario_id: str) -> int:
    """Devuelve cuántos correos se soltaron para releerlos. Nunca lanza: una falla aquí no debe
    impedir la sincronización."""
    try:
        if not reclamar_marca(db, usuario_id, CLAVE, VERSION):
            return 0
        for f in avisos_pendientes(db, usuario_id):
            f.estado = "ignorado"  # no se borra: así no se vuelve a leer ni resucita
        corregir_montos_de_documentos(db, usuario_id)
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
