"""
Tablas de gastos compartidos (estilo Splitwise). Los "amigos" son contactos
libres del usuario (nombre/teléfono): no necesitan cuenta en CuadraMe y nunca
se enlazan con datos de otros usuarios de la app.

Convención: el participante "yo" se guarda con el texto 'yo'; los demás con el
id de su fila en `contactos_gasto`.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String

from app.database import Base
from app.models import gen_uuid


class ContactoGasto(Base):
    __tablename__ = "contactos_gasto"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    telefono = Column(String, default="")
    creado_en = Column(DateTime, default=datetime.utcnow)


class GrupoGasto(Base):
    __tablename__ = "grupos_gasto"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)


class MiembroGrupoGasto(Base):
    __tablename__ = "miembros_grupo_gasto"

    id = Column(String, primary_key=True, default=gen_uuid)
    grupo_id = Column(String, ForeignKey("grupos_gasto.id", ondelete="CASCADE"), nullable=False, index=True)
    contacto_id = Column(String, ForeignKey("contactos_gasto.id", ondelete="CASCADE"), nullable=False)


class GastoCompartido(Base):
    __tablename__ = "gastos_compartidos"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    grupo_id = Column(String, nullable=True, index=True)
    movimiento_id = Column(String, nullable=True)  # movimiento propio creado junto al gasto
    descripcion = Column(String, nullable=False)
    total = Column(Float, nullable=False)
    moneda = Column(String, default="COP")
    pagador_id = Column(String, nullable=False)  # 'yo' o id de contacto
    modo = Column(String, default="iguales")
    fecha = Column(DateTime, default=datetime.utcnow)
    creado_en = Column(DateTime, default=datetime.utcnow)


class ParteGasto(Base):
    __tablename__ = "partes_gasto"

    id = Column(String, primary_key=True, default=gen_uuid)
    gasto_id = Column(String, ForeignKey("gastos_compartidos.id", ondelete="CASCADE"), nullable=False, index=True)
    participante_id = Column(String, nullable=False)  # 'yo' o id de contacto
    monto = Column(Float, nullable=False)


class LiquidacionGasto(Base):
    """Un pago entre dos personas que reduce lo que se debían."""
    __tablename__ = "liquidaciones_gasto"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    grupo_id = Column(String, nullable=True)
    de_id = Column(String, nullable=False)  # quien paga ('yo' o contacto)
    a_id = Column(String, nullable=False)   # quien recibe
    monto = Column(Float, nullable=False)
    moneda = Column(String, default="COP")
    nota = Column(String, default="")
    fecha = Column(DateTime, default=datetime.utcnow)
