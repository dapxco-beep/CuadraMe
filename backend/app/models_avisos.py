"""Avisos de actividad para la administración.

`eventos_actividad`: una fila por cosa que vale la pena saber (registro nuevo, primera cuenta,
Gmail conectado...). Guarda el hecho, NUNCA datos financieros (montos, descripciones, nombres).
`ajustes_avisos`: preferencias de ruido del administrador (qué avisa por push/correo, silencio, resumen).
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text

from app.database import Base
from app.models import gen_uuid


class EventoActividad(Base):
    __tablename__ = "eventos_actividad"
    __table_args__ = (Index("ix_eventos_actividad_tipo_creado", "tipo", "creado_en"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    tipo = Column(String, nullable=False)
    usuario_id = Column(String, nullable=True, index=True)  # NULL en cuenta_eliminada y eventos del sistema
    # Evita duplicados: «nuevo_registro:<usuario>», «limite:<usuario>:<accion>:<dia>»... (único; NULL = sin regla).
    clave_unica = Column(String, nullable=True, unique=True)
    resumen = Column(String, nullable=False)  # frase corta, con el correo ENMASCARADO
    email = Column(String, nullable=True)  # correo completo: solo lo ve el administrador en su panel
    meta = Column(Text, nullable=True)  # JSON pequeño (acción, canal...). Sin montos ni descripciones
    # pendiente | enviado | sin_canal | silenciado | resumen | agrupado | resumido
    aviso_estado = Column(String, nullable=False, default="pendiente")
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class AjustesAvisos(Base):
    __tablename__ = "ajustes_avisos"

    usuario_id = Column(String, primary_key=True)  # el administrador (solo ADMIN_EMAIL crea esta fila)
    tipos = Column(Text, nullable=True)  # JSON {tipo: {"push": bool, "correo": bool}}
    silenciado_hasta = Column(DateTime, nullable=True)  # UTC
    resumen_diario = Column(Boolean, default=False)
    correo_error = Column(String, nullable=True)  # último motivo por el que Resend rechazó un aviso
    correo_error_en = Column(DateTime, nullable=True)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
