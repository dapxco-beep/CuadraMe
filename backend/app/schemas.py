from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CuentaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    tipo: str = "ahorro"
    saldo: float = 0
    moneda: str = "COP"
    icono: str = "🏦"


class EliminarCuentaRequest(BaseModel):
    confirmacion: str  # debe ser "ELIMINAR"


class ConfianzaAutoimportUpdate(BaseModel):
    confianza_autoimport: float = Field(ge=0.5, le=0.95)


class CategoriaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=30)
    icono: str = "🏷️"


class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=30)
    icono: Optional[str] = None
    activa: Optional[bool] = None


class CategoriaOut(BaseModel):
    id: str
    nombre: str
    icono: str
    orden: int
    activa: bool
    es_base: bool

    class Config:
        from_attributes = True


class CuentaUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    icono: Optional[str] = None


class CuentaOut(BaseModel):
    id: str
    nombre: str
    tipo: str
    saldo: float
    moneda: str
    icono: str

    class Config:
        from_attributes = True


class InvitarRequest(BaseModel):
    email: str
    rol: str = "viewer"  # viewer | editor


class InvitacionOut(BaseModel):
    id: str
    cuenta_id: str
    email_invitado: str
    rol: str
    estado: str
    creado_en: datetime

    class Config:
        from_attributes = True


class CuentaCompartidaOut(BaseModel):
    id: str
    cuenta_id: str
    usuario_id: str
    rol: str

    class Config:
        from_attributes = True


class MovimientoCreate(BaseModel):
    cuenta_id: str
    descripcion: str
    monto: float = Field(gt=0)
    tipo: Literal["income", "expense", "transfer"]
    categoria: Optional[str] = None
    fecha: Optional[datetime] = None
    notas: Optional[str] = ""


class MovimientoUpdate(BaseModel):
    """Todos los campos son opcionales: solo se cambia lo que se envía."""
    cuenta_id: Optional[str] = None
    descripcion: Optional[str] = None
    monto: Optional[float] = Field(default=None, gt=0)
    tipo: Optional[Literal["income", "expense", "transfer"]] = None
    categoria: Optional[str] = None
    fecha: Optional[datetime] = None
    notas: Optional[str] = None


class TransferenciaCreate(BaseModel):
    cuenta_origen_id: str
    cuenta_destino_id: str
    monto: float = Field(gt=0)
    fecha: Optional[datetime] = None


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


class MovimientoRapidoCreate(BaseModel):
    """Para registro sin login: Atajos de iOS, Scriptable, Tasker, reglas de correo."""
    monto: float = Field(gt=0)
    tipo: Literal["income", "expense"]
    descripcion: str
    cuenta: Optional[str] = None  # nombre de cuenta a buscar (ej. "Nequi"); si no hay match usa la primera del usuario
    fuente: str = "shortcut"  # shortcut | sms | email


class RecategorizarMasivoRequest(BaseModel):
    movimiento_ids: list[str]
    categoria: str


class RecategorizarMasivoResponse(BaseModel):
    ok: bool
    actualizados: int


class MovimientoPorVozCreate(BaseModel):
    """Para registro por voz/Siri: se manda la frase dicha tal cual, sin
    estructurar. El backend interpreta monto/tipo/descripción."""
    texto: str
    cuenta: Optional[str] = None


class MovimientoPorVozResponse(BaseModel):
    ok: bool
    entendido: bool
    movimiento: Optional[MovimientoOut] = None
    mensaje: str


class VidasAhorcadoResponse(BaseModel):
    vidas_disponibles: int
    racha_actual: int
    mejor_racha: int


class PartidaAhorcadoOut(BaseModel):
    id: str
    progreso: str  # ej: "A _ O R _ O"
    letras_intentadas: list[str]
    intentos_restantes: int
    pista: str
    estado: str  # jugando | ganada | perdida
    palabra: Optional[str] = None  # solo se revela si estado != jugando


class AdivinarLetraRequest(BaseModel):
    letra: str


class ReglaCategoriaCreate(BaseModel):
    patron: str = Field(min_length=1)
    categoria: str
    tipo: Optional[str] = None
    prioridad: int = 0


class ReglaCategoriaOut(BaseModel):
    id: str
    patron: str
    categoria: str
    tipo: Optional[str]
    prioridad: int

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
    limite: float = Field(gt=0)
    periodo: str = "monthly"
    alerta_pct: int = 80


class PresupuestoOut(BaseModel):
    id: str
    categoria: str
    periodo: str
    limite: float
    alerta_pct: int
    sobre_ajuste: float = 0
    activo: bool

    class Config:
        from_attributes = True


class MoverSobreRequest(BaseModel):
    presupuesto_origen_id: str
    presupuesto_destino_id: str
    monto: float = Field(gt=0)


class DisponibleCategoria(BaseModel):
    categoria: str
    limite: float
    gastado: float
    disponible: float
    disponible_por_dia: float
    pct_usado: float
    dias_restantes_mes: int


class DisponibleHoy(BaseModel):
    disponible_total_hoy: float
    disponible_total_mes: float
    dias_restantes_mes: int
    categorias: list[DisponibleCategoria]


class EnMiBolsillo(BaseModel):
    """'In My Pocket': cuánto es realmente tuyo para gastar, después de
    descontar compromisos ya conocidos (recurrentes pendientes y aportes
    a metas), no solo el saldo crudo de las cuentas."""
    saldo_total: float
    recurrentes_pendientes_mes: float
    aportes_comprometidos_mes: float
    disponible_real: float
    disponible_real_por_dia: float
    dias_restantes_mes: int


class EdadDelDinero(BaseModel):
    """'Age of Money' (YNAB): promedio de días entre que el dinero entra
    a una cuenta y se gasta. Más alto = más colchón real, no solo saldo."""
    dias: int
    tendencia: str  # subiendo | bajando | estable
    mensaje: str


class TendenciaMes(BaseModel):
    mes: str
    ingresos: float
    gastos: float
    ahorro: float


class Proyeccion(BaseModel):
    gasto_proyectado_mes: float
    dias_transcurridos: int
    dias_restantes_mes: int
    ritmo_diario: float


class TendenciasResponse(BaseModel):
    meses: list[TendenciaMes]
    proyeccion: Proyeccion


class FlujoCajaMes(BaseModel):
    mes: str
    saldo_proyectado: float
    ingresos_esperados: float
    gastos_esperados: float


class FlujoCajaFuturo(BaseModel):
    saldo_actual: float
    meses: list[FlujoCajaMes]


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
    monto_objetivo: float = Field(gt=0)
    monto_actual: float = Field(default=0, ge=0)
    icono: str = "🎯"
    fecha_objetivo: Optional[datetime] = None
    aporte_automatico: Optional[float] = Field(default=None, gt=0)
    dia_aporte: int = Field(default=1, ge=1, le=31)
    cuenta_origen_id: Optional[str] = None


class MetaUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    monto_objetivo: Optional[float] = None
    monto_actual: Optional[float] = None
    icono: Optional[str] = None
    fecha_objetivo: Optional[datetime] = None
    activa: Optional[bool] = None


class MetaOut(BaseModel):
    id: str
    nombre: str
    descripcion: str
    monto_objetivo: float
    monto_actual: float
    icono: str
    fecha_inicio: datetime
    fecha_objetivo: Optional[datetime]
    aporte_automatico: Optional[float]
    dia_aporte: int
    cuenta_origen_id: Optional[str]
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
    monto: float = Field(gt=0)
    tipo: str = "expense"
    categoria: str = "Otros"
    cuenta_id: Optional[str] = None
    dia_del_mes: int = Field(default=1, ge=1, le=31)
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


class RecurrenteSugerido(BaseModel):
    descripcion: str
    categoria: str
    tipo: str
    monto_promedio: float
    cuenta_id: Optional[str]
    dia_del_mes: int
    ocurrencias: int
    ultima_fecha: datetime


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
    monto_pagado: float = Field(gt=0)
    crear_movimiento: bool = True


class MarcarPagadoRequest(BaseModel):
    crear_movimiento: bool = True


# ── Correos bancarios (Gmail) ──────────────────────────────────────

class GmailEstado(BaseModel):
    conectado: bool
    email: Optional[str] = None
    etiqueta: str = "gastos"


class CorreoGastoOut(BaseModel):
    id: str
    remitente: str
    asunto: str
    snippet: str
    recibido_en: Optional[datetime]
    monto: float
    moneda: str
    comercio: str
    categoria_sugerida: str
    tipo_sugerido: str
    confianza: float
    estado: str
    movimiento_id: Optional[str]

    class Config:
        from_attributes = True


class CorreoGastoUpdate(BaseModel):
    monto: Optional[float] = None
    comercio: Optional[str] = None
    categoria: Optional[str] = None
    tipo: Optional[str] = None


class AprobarCorreoRequest(BaseModel):
    cuenta_id: str


class SincronizarCorreosResponse(BaseModel):
    ok: bool
    nuevos: int
    omitidos: int
    error: Optional[str] = None


# ── Notificaciones push ──────────────────────────────────────

class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class VapidPublicKeyResponse(BaseModel):
    public_key: str


# ── Alertas proactivas ──────────────────────────────────────

class ComisionDetectada(BaseModel):
    descripcion: str
    total_mes: float
    veces: int


class CobroDuplicado(BaseModel):
    descripcion: str
    monto: float
    fecha_1: datetime
    fecha_2: datetime
    movimiento_id_1: str
    movimiento_id_2: str


class AlertasProactivasResponse(BaseModel):
    comisiones: list[ComisionDetectada]
    cobros_duplicados: list[CobroDuplicado]


# ── Insights (IA) ──────────────────────────────────────

class Anomalia(BaseModel):
    categoria: str
    monto_actual: float
    promedio_historico: float
    variacion_pct: float


class ResumenSemanal(BaseModel):
    ingresos: float
    gastos: float
    ahorro: float
    top_categorias: list[dict]
    anomalias: list[Anomalia]
    texto: str


class PreguntarRequest(BaseModel):
    pregunta: str = Field(min_length=1, max_length=500)


class PreguntarResponse(BaseModel):
    respuesta: str


# ── Conciliación de extractos ──────────────────────────────────────

class ProcesarExtractoRequest(BaseModel):
    pdf_base64: str = Field(max_length=20_000_000)  # ~15 MB de PDF una vez decodificado
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
    categoria_sugerida: Optional[str] = None


class ProcesarExtractoResponse(BaseModel):
    ok: bool
    historial_id: Optional[str] = None
    banco_detectado: Optional[str] = None
    total_movimientos: int = 0
    exactos: int = 0
    aproximados: int = 0
    faltantes: int = 0
    descartados: int = 0
    review: list[MovimientoReview] = []
    error: Optional[str] = None


class ImportarFaltantesRequest(BaseModel):
    fingerprints: list[str]
    categorias: Optional[dict[str, str]] = None  # fingerprint -> categoría elegida por el usuario, si la cambió


class HistorialExtractoOut(BaseModel):
    id: str
    cuenta_id: str
    banco_detectado: str
    total_movimientos: int
    exactos: int
    aproximados: int
    faltantes: int
    descartados: int = 0
    importados: int
    estado: str
    creado_en: datetime

    class Config:
        from_attributes = True
