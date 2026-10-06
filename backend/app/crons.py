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
