"""
Colectas (vacas): inscripción del equipo, paseo, regalo. Las lleva UNA persona (el organizador) y los demás son
sus contactos de gastos compartidos: no necesitan cuenta. Convención de participante igual a models_gastos:
'yo' o el id de su fila en `contactos_gasto`.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String

from app.database import Base
from app.models import gen_uuid


class Colecta(Base):
    __tablename__ = "colectas"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)  # organizador
    nombre = Column(String, nullable=False)
    descripcion = Column(String, default="")
    modo = Column(String, default="por_persona")  # por_persona | meta_total
    meta_total = Column(Float, default=0)  # suma de lo que debe cada participante
    moneda = Column(String, default="COP")
    fecha_limite = Column(DateTime, nullable=True)
    cuenta_id = Column(String, nullable=True)  # donde se registran como ingreso los pagos (opcional)
    token_publico = Column(String, nullable=True, unique=True, index=True)  # enlace de solo lectura; null = no compartida
    estado = Column(String, default="abierta")  # abierta | cerrada
    creado_en = Column(DateTime, default=datetime.utcnow)


class AporteColecta(Base):
    """Lo que debe poner un participante. Lo pagado es la suma de sus PagoColecta."""
    __tablename__ = "aportes_colecta"

    id = Column(String, primary_key=True, default=gen_uuid)
    colecta_id = Column(String, ForeignKey("colectas.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(String, nullable=False, index=True)
    participante_id = Column(String, nullable=False)  # 'yo' | id de contacto
    debe = Column(Float, nullable=False, default=0)


class PagoColecta(Base):
    __tablename__ = "pagos_colecta"

    id = Column(String, primary_key=True, default=gen_uuid)
    aporte_id = Column(String, ForeignKey("aportes_colecta.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(String, nullable=False, index=True)
    monto = Column(Float, nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow)
    movimiento_id = Column(String, nullable=True)  # ingreso que se registró en una cuenta, si se pidió
