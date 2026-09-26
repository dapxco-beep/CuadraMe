import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Cuenta(Base):
    __tablename__ = "cuentas"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)  # UUID de Supabase Auth
    nombre = Column(String, nullable=False)
    tipo = Column(String, default="ahorro")  # ahorro | efectivo | credito | inversion
    saldo = Column(Float, default=0)
    moneda = Column(String, default="COP")
    icono = Column(String, default="🏦")

    movimientos = relationship("Movimiento", back_populates="cuenta")


class Movimiento(Base):
    __tablename__ = "movimientos"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    cuenta_id = Column(String, index=True, nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow, index=True)
    descripcion = Column(String, nullable=False)
    categoria = Column(String, default="Otros")
    tipo = Column(String, nullable=False)  # income | expense | transfer
    monto = Column(Float, nullable=False)
    fuente = Column(String, default="manual")  # manual | csv_import | ai | sms
    notas = Column(String, default="")

    cuenta = relationship(
        "Cuenta",
        back_populates="movimientos",
        primaryjoin="foreign(Movimiento.cuenta_id) == Cuenta.id",
    )


class Presupuesto(Base):
    __tablename__ = "presupuestos"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    categoria = Column(String, nullable=False)
    periodo = Column(String, default="monthly")
    limite = Column(Float, nullable=False)
    alerta_pct = Column(Integer, default=80)
    activo = Column(Boolean, default=True)
