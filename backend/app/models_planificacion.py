"""Modelo de la configuración de planificación. Tabla nueva (create_all la crea
sola) en vez de agregar columnas a perfiles/presupuestos: no toca los datos ni
el esquema existente."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database import Base


class ConfigPlanificacion(Base):
    __tablename__ = "config_planificacion"

    usuario_id = Column(String, primary_key=True)
    dia_pago = Column(Integer, nullable=True)  # 1-31: ancla de la quincena
    periodo_defecto = Column(String, default="monthly")  # para presupuestos nuevos
    regla_necesidades = Column(Float, default=50)
    regla_deseos = Column(Float, default=30)
    regla_ahorro = Column(Float, default=20)
    arrastre_ids = Column(String, default="[]")  # JSON: ids de presupuestos que arrastran sobrante
    alertas_proyeccion = Column(String, default="{}")  # JSON {presupuesto_id: clave de periodo ya avisado}
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
