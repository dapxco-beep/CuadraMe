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


# ── Metas de ahorro ──────────────────────────────────────

class MetaCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = ""
    monto_objetivo: float
    monto_actual: float = 0
    fecha_objetivo: Optional[datetime] = None


class MetaUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    monto_objetivo: Optional[float] = None
    monto_actual: Optional[float] = None
    fecha_objetivo: Optional[datetime] = None
    activa: Optional[bool] = None


class MetaOut(BaseModel):
    id: str
    nombre: str
    descripcion: str
    monto_objetivo: float
    monto_actual: float
    fecha_inicio: datetime
    fecha_objetivo: Optional[datetime]
    activa: bool
    progreso_pct: float
    faltante: float
    dias_restantes: Optional[int]
    eta_meses: Optional[int]
    aporte_necesario_mes: Optional[int]
    completada: bool


# ── Gastos recurrentes ──────────────────────────────────────

class RecurrenteCreate(BaseModel):
    nombre: str
    monto: float
    tipo: str = "expense"
    categoria: str = "Otros"
    cuenta_id: Optional[str] = None
    dia_del_mes: int = 1
    alerta_dias_antes: int = 2
    notas: Optional[str] = ""


class RecurrenteOut(BaseModel):
    id: str
    nombre: str
    monto: float
    tipo: str
    categoria: str
    cuenta_id: Optional[str]
    dia_del_mes: int
    alerta_dias_antes: int
    ultima_vez: Optional[datetime]
    notas: str
    activo: bool
    estado: str
    dias_para_vencer: int
    ya_este_mes: bool


# ── Deudas ──────────────────────────────────────

class DeudaCreate(BaseModel):
    nombre: str
    tipo: str = "credito"
    entidad: Optional[str] = ""
    saldo_inicial: float
    saldo_actual: Optional[float] = None
    tasa_mensual: float = 0
    cuota_mensual: float = 0
    fecha_fin: Optional[datetime] = None
    dia_corte: Optional[int] = None
    dia_pago: int = 1
    cuenta_pago_id: Optional[str] = None
    notas: Optional[str] = ""


class DeudaOut(BaseModel):
    id: str
    nombre: str
    tipo: str
    entidad: str
    saldo_inicial: float
    saldo_actual: float
    tasa_mensual: float
    tasa_ea: float
    cuota_mensual: float
    interes_este_mes: float
    abono_capital: float
    cuotas_faltantes: Optional[int]
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]
    dia_corte: Optional[int]
    dia_pago: int
    dias_para_pago: int
    dias_para_corte: Optional[int]
    cuenta_pago_id: Optional[str]
    notas: str
    urgencia: str
    activa: bool


class PagarDeudaRequest(BaseModel):
    monto_pagado: float
    crear_movimiento: bool = True


class MarcarPagadoRequest(BaseModel):
    crear_movimiento: bool = True


# ── Conciliación de extractos ──────────────────────────────────────

class ProcesarExtractoRequest(BaseModel):
    pdf_base64: str
    cuenta_id: str
    password: Optional[str] = ""


class MovimientoReview(BaseModel):
    fecha: str
    descripcion: str
    monto: float
    tipo: str
    referencia: Optional[str] = ""
    fingerprint: str
    estado: str  # exacto | aproximado | faltante
    match_id: Optional[str] = None


class ProcesarExtractoResponse(BaseModel):
    ok: bool
    historial_id: Optional[str] = None
    banco_detectado: Optional[str] = None
    total_movimientos: int = 0
    exactos: int = 0
    aproximados: int = 0
    faltantes: int = 0
    review: list[MovimientoReview] = []
    error: Optional[str] = None


class ImportarFaltantesRequest(BaseModel):
    fingerprints: list[str]


class HistorialExtractoOut(BaseModel):
    id: str
    cuenta_id: str
    banco_detectado: str
    total_movimientos: int
    exactos: int
    aproximados: int
    faltantes: int
    importados: int
    estado: str
    creado_en: datetime

    class Config:
        from_attributes = True
