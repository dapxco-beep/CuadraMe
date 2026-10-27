"""
Hogares (pareja, familia, compañeros de casa): un libro común de gastos entre personas que SÍ tienen cuenta.

Permisos por MEMBRESÍA, no por `usuario_id`: solo un miembro activo ve el hogar y nadie ve nada personal de otro
(cuentas, movimientos, categorías). Por eso las tablas del libro (gastos, partes, pagos) NO tienen columna
`usuario_id`: apuntan a `miembros_hogar.id` y así el borrado de la cuenta de UNA persona no se lleva por delante
lo que los demás ya aportaron; su membresía se anonimiza («Ex miembro») en vez de borrarse (ver derechos_titular).
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String

from app.database import Base
from app.models import gen_uuid


class Hogar(Base):
    __tablename__ = "hogares"

    id = Column(String, primary_key=True, default=gen_uuid)
    nombre = Column(String, nullable=False)
    moneda = Column(String, default="COP")
    creado_por = Column(String, nullable=False)  # id de usuario de quien lo creó (solo informativo)
    creado_en = Column(DateTime, default=datetime.utcnow)


class MiembroHogar(Base):
    __tablename__ = "miembros_hogar"

    id = Column(String, primary_key=True, default=gen_uuid)
    hogar_id = Column(String, ForeignKey("hogares.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(String, nullable=True, index=True)  # null = «Ex miembro» (borró su cuenta)
    apodo = Column(String, nullable=False)
    rol = Column(String, default="miembro")  # admin | miembro
    activo = Column(Boolean, default=True)  # false = salió o lo sacaron: ya no ve nada, sus aportes se conservan
    avisos = Column(Boolean, default=True)  # push cuando otro registra un gasto
    unido_en = Column(DateTime, default=datetime.utcnow)


class InvitacionHogar(Base):
    __tablename__ = "invitaciones_hogar"

    id = Column(String, primary_key=True, default=gen_uuid)
    hogar_id = Column(String, ForeignKey("hogares.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=True, index=True)  # si se da, solo esa cuenta puede aceptar
    invitado_por = Column(String, nullable=False)  # id de usuario del admin
    estado = Column(String, default="pendiente")  # pendiente | aceptada | cancelada
    vence_en = Column(DateTime, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)


class GastoHogar(Base):
    __tablename__ = "gastos_hogar"

    id = Column(String, primary_key=True, default=gen_uuid)
    hogar_id = Column(String, ForeignKey("hogares.id", ondelete="CASCADE"), nullable=False, index=True)
    descripcion = Column(String, nullable=False)
    categoria = Column(String, nullable=True)
    total = Column(Float, nullable=False)
    moneda = Column(String, default="COP")
    modo = Column(String, default="iguales")
    pagador_id = Column(String, nullable=False)  # miembros_hogar.id
    creado_por_id = Column(String, nullable=False)  # miembros_hogar.id
    fecha = Column(DateTime, default=datetime.utcnow)
    creado_en = Column(DateTime, default=datetime.utcnow)


class ParteGastoHogar(Base):
    __tablename__ = "partes_gasto_hogar"

    id = Column(String, primary_key=True, default=gen_uuid)
    gasto_id = Column(String, ForeignKey("gastos_hogar.id", ondelete="CASCADE"), nullable=False, index=True)
    miembro_id = Column(String, nullable=False)  # miembros_hogar.id
    monto = Column(Float, nullable=False)
    # Movimiento PERSONAL que se creó con esta parte (solo la parte de quien lo copió). Sin esto no se sabe qué gasto
    # del hogar ya está en «mis gastos» y se podría copiar dos veces. Es un id suelto, sin llave foránea: borrar el movimiento no toca el libro.
    movimiento_id = Column(String, nullable=True)


class PagoHogar(Base):
    """Liquidación: un miembro le pagó a otro lo que le debía."""
    __tablename__ = "pagos_hogar"

    id = Column(String, primary_key=True, default=gen_uuid)
    hogar_id = Column(String, ForeignKey("hogares.id", ondelete="CASCADE"), nullable=False, index=True)
    de_id = Column(String, nullable=False)  # miembros_hogar.id (quien paga)
    a_id = Column(String, nullable=False)  # miembros_hogar.id (quien recibe)
    monto = Column(Float, nullable=False)
    moneda = Column(String, default="COP")
    nota = Column(String, default="")
    creado_por_id = Column(String, nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow)
