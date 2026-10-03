"""Modelos de Impuestos (Colombia) y Cierre de mes. Viven en su propio archivo
(como models_patrimonio.py): se registran en Base.metadata al importarse desde
los routers, así create_all, el backup y "Eliminar mi cuenta" (que recorre las
tablas con usuario_id) los cubren sin tocar nada más."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, UniqueConstraint

from app.database import Base
from app.models import gen_uuid


class AjusteUsuario(Base):
    """Preferencias por usuario que no caben en `perfiles`: cuenta exenta del
    4x1000 y si quiere recibir el cierre de mes también por correo."""
    __tablename__ = "ajustes_usuario"

    usuario_id = Column(String, primary_key=True)
    cuenta_exenta_gmf_id = Column(String, nullable=True)  # la ley permite UNA cuenta exenta por titular
    cierre_correo = Column(Boolean, default=False)  # opt-in: por defecto NO se manda correo
    email_cierre = Column(String, nullable=True)  # correo guardado al activarlo (los crons no tienen el token del usuario)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarcaFiscal(Base):
    """Un gasto que el usuario marcó (o descartó) como 'posiblemente deducible',
    con una nota/etiqueta opcional de soporte (ej. 'factura en el correo, mar 2026').
    NO guarda archivos: solo texto."""
    __tablename__ = "marcas_fiscales"
    __table_args__ = (UniqueConstraint("usuario_id", "movimiento_id", name="uq_marca_fiscal_usuario_mov"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    movimiento_id = Column(String, nullable=False, index=True)
    categoria_fiscal = Column(String, nullable=False)  # ver impuestos.CATEGORIAS_FISCALES
    soporte = Column(String, default="")
    estado = Column(String, default="confirmada")  # confirmada | descartada
    creado_en = Column(DateTime, default=datetime.utcnow)


class CierreMes(Base):
    """Informe de cierre mensual ya generado. Una fila por (usuario, mes): es lo
    que hace idempotente al cron (si ya existe no se regenera ni se re-notifica)."""
    __tablename__ = "cierres_mes"
    __table_args__ = (UniqueConstraint("usuario_id", "mes", name="uq_cierre_usuario_mes"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    mes = Column(String, nullable=False)  # 'YYYY-MM'
    datos = Column(String, default="{}")  # JSON del informe (ver cierre_mensual.generar_cierre)
    notificado_push = Column(Boolean, default=False)
    notificado_correo = Column(Boolean, default=False)
    visto = Column(Boolean, default=False)
    creado_en = Column(DateTime, default=datetime.utcnow)
