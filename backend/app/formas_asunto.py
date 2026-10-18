"""Contador anónimo de «formas de asunto» que fallan (opt-in).

Para qué: saber qué plantillas de correo de bancos y billeteras no estamos leyendo, y así agregarlas al lector
estándar. NO es entrenamiento: no hay ningún modelo, no se guarda contenido de correos y nada de lo que una
persona enseña (sus reglas personales) sale de su cuenta.

Qué entra: SOLO el esqueleto del asunto armado con un vocabulario fijo de notificaciones (ver
`reglas_correo.esqueleto_anonimo`: sin dígitos, montos, comercios ni nombres) y el dominio del remitente
(nunca la dirección completa; los correos gratuitos no cuentan). Sin usuario: la tabla no sabe quién lo envió.

Quién lo alimenta: únicamente quien activó la finalidad opcional «estadisticas_anonimas» (apagada por defecto,
revocable). Sin esa autorización registrar_forma no hace nada.
"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import FormaAsuntoFallida
from app.reglas_correo import dominio_anonimo, esqueleto_anonimo

logger = logging.getLogger(__name__)

FINALIDAD = "estadisticas_anonimas"


def registrar_forma(db: Session, usuario_id: str, remitente: str, asunto: str) -> bool:
    """Suma 1 a la forma de este asunto si la persona aceptó compartir estadísticas anónimas. Tolerante a fallos:
    nunca debe romper la lectura de correos. No hace commit (lo hace quien la llama con su lote)."""
    try:
        from app.routers.consentimientos import tiene_consentimiento  # import tardío: evita un ciclo de módulos

        if not tiene_consentimiento(db, usuario_id, FINALIDAD):
            return False
        esq = esqueleto_anonimo(asunto)
        if not esq:
            return False
        dominio = dominio_anonimo(remitente)
        fila = db.query(FormaAsuntoFallida).filter(FormaAsuntoFallida.esqueleto == esq, FormaAsuntoFallida.dominio == dominio).first()
        ahora = datetime.utcnow()
        if fila is None:
            db.add(FormaAsuntoFallida(esqueleto=esq, dominio=dominio, conteo=1, primera_vez=ahora, ultima_vez=ahora))
        else:
            fila.conteo = (fila.conteo or 0) + 1
            fila.ultima_vez = ahora
        db.flush()
        return True
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo anotar la forma de asunto (se ignora)")
        return False


def mas_frecuentes(db: Session, limite: int = 50) -> list[dict]:
    filas = (db.query(FormaAsuntoFallida).order_by(FormaAsuntoFallida.conteo.desc(), FormaAsuntoFallida.ultima_vez.desc())
             .limit(max(1, min(limite, 200))).all())
    return [{"esqueleto": f.esqueleto, "dominio": f.dominio, "conteo": f.conteo,
             "ultima_vez": f.ultima_vez.isoformat() if f.ultima_vez else None} for f in filas]
