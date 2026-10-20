"""Registro de lo que hace el autoarreglo (app/autoarreglo.py): una fila por cambio, agrupadas en lotes.

Sirve para dos cosas: mostrarle a la persona QUÉ se ordenó solo («Ver qué hice») y poder DESHACERLO por lote.
Solo guarda montos, ids y descripciones cortas de movimientos (más la revisión del extracto en `antes` de las filas
de tipo `historial`, para poder restaurarla). Como esa revisión sale de correos, la tabla NO se respalda (backup.py)."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, String, Text

from app.database import Base
from app.models import gen_uuid


class ArregloAuto(Base):
    __tablename__ = "arreglos_auto"
    __table_args__ = (Index("ix_arreglos_auto_usuario_lote", "usuario_id", "lote_id"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    lote_id = Column(String, nullable=False)
    # mover_cuenta | corregir_tipo | corregir_monto | quitar_repetido | crear_linea | ajuste_inicial | historial | saldo
    tipo = Column(String, nullable=False)
    entidad_id = Column(String, nullable=True)  # movimiento, extracto (historial) o cuenta
    antes = Column(Text, nullable=True)  # JSON mínimo del estado anterior
    despues = Column(Text, nullable=True)  # JSON del estado posterior (sirve para detectar cambios hechos después)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    revertido_en = Column(DateTime, nullable=True)
