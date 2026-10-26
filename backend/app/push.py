"""
Envío de Web Push (notificaciones del navegador, funcionan en Android y en
iOS 16.4+ solo si la PWA está "instalada" a pantalla de inicio). Usa VAPID
para autenticar el servidor ante los navegadores, sin depender de Firebase.
"""
import json
import logging

from py_vapid import Vapid01
from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PushSubscription

logger = logging.getLogger("app.push")


def _private_key_pem() -> str:
    return settings.vapid_private_key_pem.replace("\\n", "\n")


def _vapid() -> Vapid01:
    """La clave privada VAPID como OBJETO. pywebpush solo lee un PEM si recibe la ruta de un archivo o un objeto de
    clave: si le pasas el TEXTO del PEM lo interpreta como base64 y falla con «Could not deserialize key data».
    Ese fallo se tragaba en silencio y por eso ningún aviso salía (ni a iPhone ni a Android)."""
    return Vapid01.from_pem(_private_key_pem().strip().encode())


def _url_hash(url: str) -> str:
    """La PWA usa HashRouter: la ruta '/presupuesto' real es '/#/presupuesto'.
    Sin esto, tocar la notificación abre una URL que no existe."""
    if url.startswith("/#"):
        return url
    return "/#" + (url if url.startswith("/") else "/" + url)


def enviar_push(db: Session, usuario_id: str, titulo: str, cuerpo: str, url: str = "/",
                boton: str | None = None) -> int:
    """Envía a todas las suscripciones activas del usuario. Retorna cuántas
    tuvieron éxito. Elimina suscripciones que ya no son válidas (410/404)."""
    if not settings.vapid_private_key_pem:
        return 0

    try:
        vapid = _vapid()
    except Exception as e:
        # Clave mal puesta en el servidor: se dice en el registro (sin la clave) en vez de fallar por dentro.
        logger.error("push: la clave VAPID del servidor no se puede leer (%s)", type(e).__name__)
        return 0

    subs = db.query(PushSubscription).filter(PushSubscription.usuario_id == usuario_id).all()
    enviados = 0

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json.dumps({"title": titulo, "body": cuerpo, "url": _url_hash(url),
                                 **({"boton": boton} if boton else {})}),
                vapid_private_key=vapid,
                vapid_claims={"sub": settings.vapid_subject},
            )
            enviados += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                db.delete(sub)
                db.commit()
            else:
                # Apple/Google rechazaron el aviso (p. ej. 403 clave rechazada, 400 mal formado): antes se perdía sin rastro.
                servicio = (sub.endpoint.split("/")[2] if "//" in sub.endpoint else "desconocido")
                logger.warning("push: %s respondió %s", servicio, status)
        except Exception as e:
            # Red caída, VAPID inválido, clave mal formada... Un fallo de envío
            # nunca debe tumbar el cron ni a los demás usuarios. Se registra solo
            # el tipo de error (sin endpoint, claves ni datos personales).
            logger.warning("push: envío fallido (%s)", type(e).__name__)

    return enviados
