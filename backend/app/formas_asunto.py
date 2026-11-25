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
import re
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


def registrar_aviso(db: Session, usuario_id: str, app: str, titulo: str, texto: str) -> bool:
    """Igual que `registrar_forma` pero para NOTIFICACIONES de apps de bancos (atajo de iPhone): suma 1 a la forma
    del aviso que el lector no entendió, con dominio «aviso:<app>». Solo el esqueleto de vocabulario fijo; nunca el
    texto, montos ni nombres. Solo cuenta si la persona aceptó las estadísticas anónimas. No hace commit."""
    try:
        from app.routers.consentimientos import tiene_consentimiento  # import tardío: evita un ciclo de módulos

        if not tiene_consentimiento(db, usuario_id, FINALIDAD):
            return False
        esq = esqueleto_anonimo(f"{titulo or ''}. {texto or ''}")
        if not esq:
            return False
        dominio = f"aviso:{(app or '')[:30].strip().lower()}"
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
        logger.exception("No se pudo anotar la forma de aviso (se ignora)")
        return False


# Pantallas que se abren (solo la ruta de la app, sin identificadores ni datos): «/presupuesto?tab=fijos», «/movimientos/:id».
DOMINIO_PANTALLA = "pantalla"
_RUTA_PANTALLA = re.compile(r"^/[a-z0-9/_:-]{0,60}(\?tab=[a-z_]{1,24})?$")


def ruta_valida(ruta: str) -> bool:
    return bool(ruta) and len(ruta) <= 90 and bool(_RUTA_PANTALLA.match(ruta))


def registrar_pantalla(db: Session, usuario_id: str, ruta: str) -> bool:
    """Suma 1 a la pantalla abierta si la persona aceptó las estadísticas anónimas. Solo guarda la ruta de la app (sin
    usuario, sin identificadores). Sirve para saber qué se usa y qué no. No hace commit."""
    try:
        from app.routers.consentimientos import tiene_consentimiento  # import tardío: evita un ciclo de módulos

        if not ruta_valida(ruta) or not tiene_consentimiento(db, usuario_id, FINALIDAD):
            return False
        esq = f"pantalla {ruta}"
        fila = db.query(FormaAsuntoFallida).filter(FormaAsuntoFallida.esqueleto == esq, FormaAsuntoFallida.dominio == DOMINIO_PANTALLA).first()
        ahora = datetime.utcnow()
        if fila is None:
            db.add(FormaAsuntoFallida(esqueleto=esq, dominio=DOMINIO_PANTALLA, conteo=1, primera_vez=ahora, ultima_vez=ahora))
        else:
            fila.conteo = (fila.conteo or 0) + 1
            fila.ultima_vez = ahora
        db.flush()
        return True
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo anotar la pantalla (se ignora)")
        return False


def pantallas_mas_usadas(db: Session, limite: int = 100) -> list[dict]:
    filas = (db.query(FormaAsuntoFallida).filter(FormaAsuntoFallida.dominio == DOMINIO_PANTALLA)
             .order_by(FormaAsuntoFallida.conteo.desc()).limit(max(1, min(limite, 300))).all())
    return [{"ruta": f.esqueleto[len("pantalla "):], "aperturas": f.conteo,
             "ultima_vez": f.ultima_vez.isoformat() if f.ultima_vez else None} for f in filas]


def mas_frecuentes(db: Session, limite: int = 50) -> list[dict]:
    filas = (db.query(FormaAsuntoFallida).filter(FormaAsuntoFallida.dominio != DOMINIO_PANTALLA)
             .order_by(FormaAsuntoFallida.conteo.desc(), FormaAsuntoFallida.ultima_vez.desc())
             .limit(max(1, min(limite, 200))).all())
    return [{"esqueleto": f.esqueleto, "dominio": f.dominio, "conteo": f.conteo,
             "ultima_vez": f.ultima_vez.isoformat() if f.ultima_vez else None} for f in filas]
