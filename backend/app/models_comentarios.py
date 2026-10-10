"""Buzón de opinión: comentarios, ideas, problemas y dudas de las personas que usan CuadraMe.

Guarda el texto que la persona escribe, la pantalla donde estaba y un resumen corto del
dispositivo. NUNCA datos financieros. `nota_admin` es interna (solo la ve la administración);
`respuesta_publica` sí la ve quien escribió el comentario.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text

from app.database import Base
from app.models import gen_uuid

TIPOS = ("sugerencia", "problema", "pregunta", "elogio", "banco")  # «banco»: «Mi banco no aparece»
ESTADOS = ("nuevo", "visto", "en_curso", "resuelto", "descartado")


class Comentario(Base):
    __tablename__ = "comentarios"
    __table_args__ = (Index("ix_comentarios_estado_creado", "estado", "creado_en"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True)  # copia del correo, para poder responder
    tipo = Column(String, nullable=False, default="sugerencia")  # sugerencia | problema | pregunta | elogio | banco
    mensaje = Column(Text, nullable=False)
    pantalla = Column(String, nullable=True)  # ruta donde estaba (máx 120)
    version_app = Column(String, nullable=True)
    dispositivo = Column(String, nullable=True)  # «móvil · Chrome»
    puede_contactar = Column(Boolean, default=True)
    estado = Column(String, nullable=False, default="nuevo")  # nuevo | visto | en_curso | resuelto | descartado
    # Solo tipo «banco»: nombre que escribió la persona y, si subió una muestra, dónde quedó (almacenamiento
    # privado; nunca una URL pública). La muestra la ve únicamente la administración y la persona la puede borrar.
    banco = Column(String, nullable=True)
    adjunto_ruta = Column(String, nullable=True)
    adjunto_nombre = Column(String, nullable=True)
    adjunto_bytes = Column(Integer, nullable=True)
    nota_admin = Column(Text, nullable=True)
    respuesta_publica = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
