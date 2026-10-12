"""Modelos de «Tu plata trabajando»: cajitas/bolsillos y tasas de referencia.

Decisión de diseño (ver docs/TU_PLATA_TRABAJANDO.md): una cajita es una PARTE del saldo de su
cuenta, no plata adicional. `Cuenta.saldo` sigue siendo el total que el banco muestra
(saldo principal + cajitas); la cajita solo dice «de este total, $X están apartados aquí y
rinden a esta tasa». Por eso mover plata entre el saldo principal y una cajita no crea
movimientos ni cambia el saldo de la cuenta: es neutral por construcción y nunca duplica
saldos en Patrimonio ni en «dinero disponible»."""
from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Index, String

from app.database import Base
from app.models import gen_uuid


class Cajita(Base):
    __tablename__ = "cajitas"
    __table_args__ = (Index("ix_cajitas_usuario_cuenta", "usuario_id", "cuenta_id"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    cuenta_id = Column(String, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    saldo = Column(Float, default=0)  # parte del saldo de la cuenta apartada aquí
    tasa_ea = Column(Float, nullable=True)  # % E.A. propia (opcional)
    tasa_fecha = Column(Date, nullable=True)  # desde cuándo vale esa tasa
    activa = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


class TasaReferencia(Base):
    """Tasas de referencia EDITABLES por la administración (nunca fijas en el código).
    Sin usuario_id: son datos públicos del sistema, iguales para todas las personas."""
    __tablename__ = "tasas_referencia"

    id = Column(String, primary_key=True, default=gen_uuid)
    entidad = Column(String, nullable=False)
    producto = Column(String, nullable=False)
    tipo = Column(String, nullable=False, default="ahorro_vista")  # ahorro_vista | saldo_principal | cdt
    tasa_ea = Column(Float, nullable=True)  # % E.A.; None = aún sin cifra verificada
    vigente_desde = Column(Date, nullable=False, default=date.today)
    fuente_url = Column(String, nullable=True)
    nota = Column(String, nullable=True)
    activa = Column(Boolean, default=True)
