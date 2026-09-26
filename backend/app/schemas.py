from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CuentaCreate(BaseModel):
    nombre: str
    tipo: str = "ahorro"
    saldo: float = 0
    moneda: str = "COP"
    icono: str = "🏦"


class CuentaOut(BaseModel):
    id: str
    nombre: str
    tipo: str
    saldo: float
    moneda: str
    icono: str

    class Config:
        from_attributes = True


class MovimientoCreate(BaseModel):
    cuenta_id: str
    descripcion: str
    monto: float
    tipo: str  # income | expense | transfer
    categoria: Optional[str] = None
    fecha: Optional[datetime] = None
    notas: Optional[str] = ""


class MovimientoOut(BaseModel):
    id: str
    cuenta_id: str
    fecha: datetime
    descripcion: str
    categoria: str
    tipo: str
    monto: float
    fuente: str
    notas: str

    class Config:
        from_attributes = True


class ClasificarRequest(BaseModel):
    descripcion: str
    monto: Optional[float] = None


class ClasificarResponse(BaseModel):
    categoria: str
    tipo: str
    confianza: float
    fuente: str  # learned | ai | default


class PresupuestoCreate(BaseModel):
    categoria: str
    limite: float
    periodo: str = "monthly"
    alerta_pct: int = 80


class PresupuestoOut(BaseModel):
    id: str
    categoria: str
    periodo: str
    limite: float
    alerta_pct: int
    activo: bool

    class Config:
        from_attributes = True


class ReporteMensual(BaseModel):
    mes: str
    ingresos: float
    gastos: float
    ahorro: float
    tasa_ahorro: float
    top_categorias: list[dict]
    salud: dict
