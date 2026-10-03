"""Modelos del módulo Patrimonio. Viven en su propio archivo para no engordar
models.py; se registran en Base.metadata al importarse (lo hace el router, que
main.py incluye), así que create_all, el backup y "Eliminar mi cuenta" (que
recorre todas las tablas con usuario_id) los cubren sin tocar nada más."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, String, UniqueConstraint

from app.database import Base
from app.models import gen_uuid


class ActivoPatrimonio(Base):
    """Un activo: CDT, fondo/ETF/acción/cripto, inmueble o vehículo.
    Una sola tabla con columnas opcionales según la clase (más simple que herencia
    y suficiente a esta escala). Los pasivos NO viven aquí: salen de `deudas`."""
    __tablename__ = "activos_patrimonio"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    clase = Column(String, nullable=False)  # cdt | fondo | etf | accion | cripto | inmueble | vehiculo
    nombre = Column(String, nullable=False)
    moneda = Column(String, default="COP")
    # CDT
    capital = Column(Float, nullable=True)
    tasa_ea = Column(Float, nullable=True)  # en %, ej. 12.5 = 12,5 % E.A.
    fecha_inicio = Column(DateTime, nullable=True)
    fecha_vencimiento = Column(DateTime, nullable=True)
    # Fondos / ETF / acciones / cripto
    ticker = Column(String, nullable=True)  # para conectar precios automáticos después
    unidades = Column(Float, nullable=True)
    costo_promedio = Column(Float, nullable=True)  # costo por unidad
    # Valor de mercado: precio por unidad (inversiones) o valor total (inmueble/vehículo)
    precio_actual = Column(Float, nullable=True)
    precio_fecha = Column(DateTime, nullable=True)
    fuente_precio = Column(String, default="manual")  # manual | <proveedor automático>
    costo_adquisicion = Column(Float, nullable=True)  # inmueble/vehículo: lo que costó
    fecha_adquisicion = Column(DateTime, nullable=True)
    notas = Column(String, default="")
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


class ValorActivo(Base):
    """Histórico de precios/valoraciones de un activo (una fila por registro)."""
    __tablename__ = "valores_activo"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    activo_id = Column(String, nullable=False, index=True)
    fecha = Column(DateTime, nullable=False)
    valor = Column(Float, nullable=False)
    fuente = Column(String, default="manual")


class FlujoActivo(Base):
    """Aportes (negativos: salen de tu bolsillo) y retiros/dividendos (positivos).
    Son la materia prima del XIRR."""
    __tablename__ = "flujos_activo"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    activo_id = Column(String, nullable=False, index=True)
    fecha = Column(DateTime, nullable=False)
    monto = Column(Float, nullable=False)
    nota = Column(String, default="")


class SnapshotPatrimonio(Base):
    """Foto mensual del patrimonio en COP. Una por (usuario, mes): guardar de nuevo
    en el mismo mes la sobrescribe, así la última del mes queda como cierre."""
    __tablename__ = "snapshots_patrimonio"
    __table_args__ = (UniqueConstraint("usuario_id", "mes", name="uq_snapshot_usuario_mes"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    mes = Column(String, nullable=False)  # 'YYYY-MM'
    fecha = Column(DateTime, default=datetime.utcnow)
    total_activos = Column(Float, default=0)  # inversiones + bienes
    total_cuentas = Column(Float, default=0)
    total_deudas = Column(Float, default=0)
    patrimonio_neto = Column(Float, default=0)
    distribucion = Column(String, default="{}")  # JSON {clase: valor_cop}
