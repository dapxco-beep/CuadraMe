"""Silencios por comercio para «por categorizar» (ver app/pendientes.py).

Una fila = «con este comercio (huella) no me molestes». `tipo`:
  no_preguntar     -> sus movimientos no cuentan como pendientes y no se sugiere regla.
  ocultar          -> sus movimientos salen de la lista de pendientes (siguen contando en informes).
  regla_descartada -> solo la SUGERENCIA de regla no vuelve a salir.
Se deshace borrando la fila. Nunca guarda montos ni descripciones: solo la huella."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, String, UniqueConstraint

from app.database import Base
from app.models import gen_uuid

TIPOS_SILENCIO = ("no_preguntar", "ocultar", "regla_descartada")


class ComercioSilenciado(Base):
    __tablename__ = "comercios_silenciados"
    __table_args__ = (
        UniqueConstraint("usuario_id", "huella", "tipo", name="uq_comercio_silenciado"),
        Index("ix_comercios_silenciados_usuario", "usuario_id"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False)
    huella = Column(String, nullable=False)
    tipo = Column(String, nullable=False, default="no_preguntar")
    creado_en = Column(DateTime, default=datetime.utcnow)
