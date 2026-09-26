import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Perfil(Base):
    __tablename__ = "perfiles"

    usuario_id = Column(String, primary_key=True)  # UUID de Supabase Auth
    plan = Column(String, default="free")  # free | pro
    stripe_customer_id = Column(String, nullable=True)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Cuenta(Base):
    __tablename__ = "cuentas"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)  # UUID de Supabase Auth
    nombre = Column(String, nullable=False)
    tipo = Column(String, default="ahorro")  # ahorro | efectivo | credito | inversion
    saldo = Column(Float, default=0)
    moneda = Column(String, default="COP")
    icono = Column(String, default="🏦")


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


class Presupuesto(Base):
    __tablename__ = "presupuestos"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    categoria = Column(String, nullable=False)
    periodo = Column(String, default="monthly")
    limite = Column(Float, nullable=False)
    alerta_pct = Column(Integer, default=80)
    activo = Column(Boolean, default=True)


class Meta(Base):
    __tablename__ = "metas"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    descripcion = Column(String, default="")
    monto_objetivo = Column(Float, nullable=False)
    monto_actual = Column(Float, default=0)
    fecha_inicio = Column(DateTime, default=datetime.utcnow)
    fecha_objetivo = Column(DateTime, nullable=True)
    activa = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


class Recurrente(Base):
    __tablename__ = "recurrentes"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    tipo = Column(String, default="expense")  # income | expense
    categoria = Column(String, default="Otros")
    cuenta_id = Column(String, nullable=True)
    dia_del_mes = Column(Integer, default=1)
    alerta_dias_antes = Column(Integer, default=2)
    ultima_vez = Column(DateTime, nullable=True)
    notas = Column(String, default="")
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


class Deuda(Base):
    __tablename__ = "deudas"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    tipo = Column(String, default="credito")  # tarjeta | credito | hipoteca | otro
    entidad = Column(String, default="")
    saldo_inicial = Column(Float, default=0)
    saldo_actual = Column(Float, default=0)
    tasa_mensual = Column(Float, default=0)
    cuota_mensual = Column(Float, default=0)
    fecha_inicio = Column(DateTime, default=datetime.utcnow)
    fecha_fin = Column(DateTime, nullable=True)
    dia_corte = Column(Integer, nullable=True)
    dia_pago = Column(Integer, default=1)
    cuenta_pago_id = Column(String, nullable=True)
    notas = Column(String, default="")
    activa = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
