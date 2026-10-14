"""Modelos del módulo Inversiones. Se construyen ENCIMA de Patrimonio: cada posición
tiene un activo "espejo" en activos_patrimonio (columna activo_id), así el valor del
portafolio alimenta el patrimonio sin doble conteo. Todo es opcional: sin filas aquí
la app no muestra nada de inversiones."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, String, UniqueConstraint

from app.database import Base
from app.models import gen_uuid


class Broker(Base):
    """Broker/plataforma/fiduciaria donde tienes inversiones. OPCIONAL: una posición
    puede existir sin broker."""
    __tablename__ = "brokers_inversion"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    pais = Column(String, default="CO")
    tipo = Column(String, default="acciones")  # acciones | etf | fondos | cripto | cdt | fiducia
    moneda = Column(String, default="COP")
    cuenta_id = Column(String, nullable=True)  # cuenta de CuadraMe asociada (opcional)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


class Posicion(Base):
    __tablename__ = "posiciones_inversion"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    broker_id = Column(String, nullable=True, index=True)
    activo_id = Column(String, nullable=True)  # espejo en activos_patrimonio
    ticker = Column(String, nullable=True)
    mercado = Column(String, default="")  # sufijo/mercado: CL, MX, SA, US...
    nombre = Column(String, nullable=False)
    tipo = Column(String, default="accion")  # accion | etf | fondo | cripto | cdt | fiducia
    moneda = Column(String, default="COP")
    # Se recalculan desde las transacciones (promedio ponderado) cuando las hay.
    cantidad = Column(Float, default=0)
    costo_promedio = Column(Float, default=0)
    precio_manual = Column(Float, nullable=True)
    precio_manual_fecha = Column(DateTime, nullable=True)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


class TransaccionInversion(Base):
    __tablename__ = "transacciones_inversion"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    posicion_id = Column(String, nullable=False, index=True)
    tipo = Column(String, nullable=False)  # compra | venta | dividendo | comision | aporte | retiro
    fecha = Column(DateTime, nullable=False)
    cantidad = Column(Float, default=0)
    precio = Column(Float, default=0)
    comision = Column(Float, default=0)
    monto = Column(Float, default=0)  # total en moneda de la posición (dividendo/aporte/retiro/comisión)
    moneda = Column(String, default="COP")
    tipo_cambio = Column(Float, nullable=True)  # COP por 1 unidad de moneda, opcional
    movimiento_id = Column(String, nullable=True)  # movimiento enlazado (traslado o ingreso)
    nota = Column(String, default="")


class Cotizacion(Base):
    """Último precio conocido por ticker. Compartida entre usuarios (dato de mercado,
    sin información personal): una consulta sirve a todos y cuida el límite del plan."""
    __tablename__ = "cotizaciones_inversion"
    __table_args__ = (UniqueConstraint("ticker", "mercado", name="uq_cotizacion_ticker_mercado"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    ticker = Column(String, nullable=False, index=True)
    mercado = Column(String, default="")
    precio = Column(Float, nullable=True)
    precio_anterior = Column(Float, nullable=True)  # precio de un día anterior, para «hoy»
    moneda = Column(String, default="")
    fecha = Column(DateTime, nullable=True)  # hora del precio
    consultada_en = Column(DateTime, nullable=True)  # último intento (también si falló)
    fuente = Column(String, default="")
    error = Column(String, default="")


class ConsultaPrecio(Base):
    """Contador de peticiones a proveedores: clave 'g:<día>' (global) o 'u:<id>:<día>'."""
    __tablename__ = "consultas_precio"

    clave = Column(String, primary_key=True)
    cantidad = Column(Float, default=0)


class PrefInversiones(Base):
    __tablename__ = "pref_inversiones"

    usuario_id = Column(String, primary_key=True)
    resumen_semanal = Column(Boolean, default=False)
