"""Aislamiento por usuario para los crons.

Un cron recorre a todos los usuarios; si el trabajo de uno lanza una excepción
(dato raro, push caído, cuenta borrada a mitad), no debe dejar sin proceso a los
demás ni dejar la sesión de base de datos "envenenada". Uso:

    corrida = Corrida(db)
    for uid in usuarios:
        with corrida.aislar(uid):
            ...trabajo del usuario (un `continue` aquí dentro es válido)...
    return {"ok": True, ..., **corrida.resumen()}

Al fallar se hace db.rollback() y se registra la traza SOLO con el id (nunca
correo ni nombre). `procesados` cuenta los que terminaron sin error.
"""
import logging
from contextlib import contextmanager

from sqlalchemy import Column, DateTime, String, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.models import gen_uuid
from app.utiles import ahora_co

logger = logging.getLogger("app.crons")


class Corrida:
    def __init__(self, db):
        self.db = db
        self.procesados = 0
        self.fallidos = 0

    @contextmanager
    def aislar(self, usuario_id):
        try:
            yield
        except Exception:
            self.db.rollback()
            self.fallidos += 1
            logger.exception("Cron: falló el procesamiento del usuario %s", usuario_id)
        else:
            self.procesados += 1

    def resumen(self) -> dict:
        return {"procesados": self.procesados, "fallidos": self.fallidos}


class MarcaCron(Base):
    """Marca de idempotencia de un cron: "a este usuario ya se le hizo X en el
    periodo Y". Una fila por (usuario, clave); `valor` es el periodo ya procesado
    (semana ISO, día, id de ocurrencia...). Tabla nueva: la crea create_all."""
    __tablename__ = "marcas_cron"
    __table_args__ = (UniqueConstraint("usuario_id", "clave", name="uq_marca_cron_usuario_clave"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)  # 'sistema' para marcas globales
    clave = Column(String, nullable=False)
    valor = Column(String, nullable=False)
    actualizado_en = Column(DateTime, default=ahora_co)


def reclamar_marca(db, usuario_id: str, clave: str, valor: str) -> bool:
    """Intenta "reclamar" (usuario, clave) para el periodo `valor`. True si es la
    primera vez (ya quedó guardado, con commit); False si ese periodo ya estaba
    marcado. Se llama ANTES de enviar: si dos ejecuciones se pisan, la restricción
    única deja pasar solo a una (la otra recibe False)."""
    fila = db.query(MarcaCron).filter(MarcaCron.usuario_id == usuario_id, MarcaCron.clave == clave).first()
    try:
        if fila is None:
            db.add(MarcaCron(usuario_id=usuario_id, clave=clave, valor=valor))
        elif fila.valor == valor:
            return False
        else:
            fila.valor = valor
            fila.actualizado_en = ahora_co()
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def liberar_marca(db, usuario_id: str, clave: str) -> None:
    """Quita la marca (para reintentar en el siguiente cron si el trabajo falló)."""
    db.query(MarcaCron).filter(MarcaCron.usuario_id == usuario_id, MarcaCron.clave == clave).delete()
    db.commit()
