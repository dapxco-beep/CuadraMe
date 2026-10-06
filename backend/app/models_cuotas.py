"""
Compras a cuotas (diferidas) de una tarjeta de crédito.

Es una VISTA DE COMPROMISO: el movimiento original de la compra ya bajó el saldo
de la tarjeta por el total, así que este plan NUNCA toca saldos; solo recuerda
cuánto, cuántas cuotas faltan y cuándo termina.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from app.database import Base
from app.models import gen_uuid


class CuotaTarjeta(Base):
    __tablename__ = "cuotas_tarjeta"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    cuenta_id = Column(String, nullable=False, index=True)  # la tarjeta
    movimiento_id = Column(String, nullable=True)  # la compra original (opcional)
    descripcion = Column(String, nullable=False)
    total = Column(Float, nullable=False)  # valor de la compra
    num_cuotas = Column(Integer, nullable=False)
    cuota_mensual = Column(Float, nullable=False)
    tasa_mensual = Column(Float, default=0)  # % mensual; 0 = sin interés
    cuotas_pagadas = Column(Integer, default=0)  # marcadas a mano (las de fechas ya vencidas se cuentan solas)
    primera_fecha = Column(DateTime, nullable=False)  # corte en que cae la primera cuota
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
