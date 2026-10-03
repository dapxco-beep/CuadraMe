"""
Uso diario del asistente de IA por usuario (tope de costos).

Solo guarda un CONTADOR por día: nunca el texto de las conversaciones.
"""
from sqlalchemy import Column, Integer, String, UniqueConstraint

from app.database import Base
from app.models import gen_uuid


class UsoAsistente(Base):
    __tablename__ = "uso_asistente"
    __table_args__ = (UniqueConstraint("usuario_id", "dia", name="uq_uso_asistente_usuario_dia"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    dia = Column(String, nullable=False)  # YYYY-MM-DD en hora Colombia
    cantidad = Column(Integer, default=0)  # mensajes que llamaron a la IA ese día
