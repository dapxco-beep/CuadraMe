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


class ExtractoTarjeta(Base):
    """Último extracto REAL que el cliente aplicó a su tarjeta (lo que dice el banco:
    pago total, pago mínimo, fecha límite). Una fila por tarjeta. Solo se escribe cuando
    el cliente pulsa 'Aplicar': nunca se actualiza solo."""
    __tablename__ = "extractos_tarjeta"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    cuenta_id = Column(String, nullable=False, unique=True)
    cupo_disponible = Column(Float, nullable=True)
    pago_total = Column(Float, nullable=True)
    pago_minimo = Column(Float, nullable=True)
    fecha_limite_pago = Column(String, nullable=True)  # AAAA-MM-DD
    fecha_corte = Column(String, nullable=True)  # AAAA-MM-DD
    actualizado_en = Column(DateTime, default=datetime.utcnow)


class DesgloseExtractoTarjeta(Base):
    """Lo que COBRÓ el banco en un extracto de tarjeta (intereses, cuota de manejo, comisiones, seguros)
    y la tasa aplicada, UNA fila por tarjeta y periodo (AAAA-MM del corte). Sirve al análisis
    «Lo que te cuesta tu plata»; todos los campos de monto son opcionales (el extracto puede no traerlos).
    Solo se escribe cuando el cliente aplica la propuesta del extracto."""
    __tablename__ = "desgloses_extracto_tarjeta"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    cuenta_id = Column(String, nullable=False, index=True)
    periodo = Column(String, nullable=False)  # AAAA-MM (mes de la fecha de corte)
    intereses_corrientes = Column(Float, nullable=True)
    intereses_mora = Column(Float, nullable=True)
    cuota_manejo = Column(Float, nullable=True)
    comisiones = Column(Float, nullable=True)
    seguros = Column(Float, nullable=True)
    tasa_ea = Column(Float, nullable=True)
    tasa_mv = Column(Float, nullable=True)
    pago_total = Column(Float, nullable=True)
    pago_minimo = Column(Float, nullable=True)
    fecha_corte = Column(String, nullable=True)
    fecha_limite_pago = Column(String, nullable=True)
    actualizado_en = Column(DateTime, default=datetime.utcnow)
