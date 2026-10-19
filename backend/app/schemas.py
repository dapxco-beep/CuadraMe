import json
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CuentaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    tipo: str = "ahorro"
    saldo: float = 0
    moneda: str = "COP"
    icono: str = "🏦"
    cupo_total: Optional[float] = Field(default=None, ge=0)
    dia_corte: Optional[int] = Field(default=None, ge=1, le=31)
    dia_pago: Optional[int] = Field(default=None, ge=1, le=31)
    tasa_ea: Optional[float] = Field(default=None, ge=0, le=200)
    alias_tarjeta: Optional[str] = Field(default=None, max_length=120)


class EliminarCuentaRequest(BaseModel):
    confirmacion: str  # debe ser "ELIMINAR"


class ConfianzaAutoimportUpdate(BaseModel):
    confianza_autoimport: float = Field(ge=0.5, le=0.95)


def _validar_icono(v):
    from app.autocat import es_emoji
    if v is None:
        return v
    v = v.strip()
    if not es_emoji(v):
        raise ValueError("El ícono debe ser un emoji (máximo 16 caracteres)")
    return v


def _validar_color(v):
    import re
    if v is None or v == "":
        return None
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        raise ValueError("El color debe tener el formato #RRGGBB")
    return v.lower()


class CategoriaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=40)
    icono: str = "🏷️"
    color: Optional[str] = None
    tipo: Literal["gasto", "ingreso", "ambos"] = "ambos"

    @field_validator("icono")
    @classmethod
    def _v_icono(cls, v):
        return _validar_icono(v)

    @field_validator("color")
    @classmethod
    def _v_color(cls, v):
        return _validar_color(v)


class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=40)
    icono: Optional[str] = None
    activa: Optional[bool] = None
    color: Optional[str] = None  # "" quita el color
    tipo: Optional[Literal["gasto", "ingreso", "ambos"]] = None

    @field_validator("icono")
    @classmethod
    def _v_icono(cls, v):
        return _validar_icono(v)

    @field_validator("color")
    @classmethod
    def _v_color(cls, v):
        # "" significa "quitar el color": se conserva para distinguirlo de "no tocar".
        return "" if v == "" else _validar_color(v)


class SubcategoriaCreate(BaseModel):
    categoria: str = Field(min_length=1, max_length=60)  # nombre de la categoría padre
    nombre: str = Field(min_length=1, max_length=40)


class SubcategoriaUpdate(BaseModel):
    nombre: str = Field(min_length=1, max_length=40)


class SubcategoriaOut(BaseModel):
    id: str
    categoria: str
    nombre: str
    orden: int = 0
    movimientos: int = 0  # cuántos movimientos la usan


class CategoriasOrden(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)


class CategoriaOut(BaseModel):
    id: str
    nombre: str
    icono: str
    orden: int
    activa: bool
    es_base: bool
    color: Optional[str] = None
    tipo: Optional[str] = "ambos"
    es_sistema: bool = False
    movimientos: int = 0  # cuántos movimientos usan esta categoría

    class Config:
        from_attributes = True


class CuentaUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    icono: Optional[str] = None
    cupo_total: Optional[float] = Field(default=None, ge=0)
    dia_corte: Optional[int] = Field(default=None, ge=1, le=31)
    dia_pago: Optional[int] = Field(default=None, ge=1, le=31)
    tasa_ea: Optional[float] = Field(default=None, ge=0, le=200)
    alias_tarjeta: Optional[str] = Field(default=None, max_length=120)


class TarjetaInfo(BaseModel):
    """Cálculos derivados de una tarjeta de crédito (ver app/tarjetas.py)."""
    cupo_usado: float
    cupo_disponible: Optional[float]
    utilizacion_pct: Optional[float]
    nivel_utilizacion: str  # sin_cupo | ok | alerta | critico
    proximo_corte: Optional[str]  # YYYY-MM-DD
    proximo_pago: Optional[str]
    dias_para_corte: Optional[int]
    dias_para_pago: Optional[int]
    pago_minimo_estimado: float
    interes_estimado: Optional[float]
    # Extracto (None si la tarjeta no tiene día de corte): lo que hay que pagar para no pagar intereses
    total_extracto: Optional[float] = None
    pagado_desde_corte: Optional[float] = None
    falta_para_evitar_intereses: Optional[float] = None
    compras_despues_corte: Optional[float] = None
    fecha_limite_pago: Optional[str] = None
    fecha_ultimo_corte: Optional[str] = None
    dias_para_limite: Optional[int] = None
    pagado_pct: Optional[float] = None
    vencido: bool = False
    # La deuda es solo el saldo que el cliente declaró al crear la tarjeta (sin historial hasta el corte)
    saldo_declarado: bool = False
    # Datos del extracto real aplicados por el cliente (ver app/extracto_tarjeta.py)
    total_del_banco: bool = False
    pago_minimo_extracto: Optional[float] = None
    pago_total_extracto: Optional[float] = None
    pago_minimo: Optional[float] = None  # el del extracto si se conoce; si no, la estimación
    pago_minimo_del_extracto: bool = False


class CuentaOut(BaseModel):
    id: str
    nombre: str
    tipo: str
    saldo: float
    moneda: str
    icono: str
    cupo_total: Optional[float] = None
    dia_corte: Optional[int] = None
    dia_pago: Optional[int] = None
    tasa_ea: Optional[float] = None
    alias_tarjeta: Optional[str] = None
    tarjeta: Optional[TarjetaInfo] = None

    class Config:
        from_attributes = True


class AjusteSaldoRequest(BaseModel):
    saldo_real: float
    nota: str = ""


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
    descripcion: str = Field(max_length=300)
    monto: float = Field(gt=0)
    tipo: Literal["income", "expense", "transfer"]
    categoria: Optional[str] = Field(default=None, max_length=60)
    subcategoria: Optional[str] = Field(default=None, max_length=40)  # opcional, debe ser de esa categoría
    fecha: Optional[datetime] = None
    notas: Optional[str] = Field(default="", max_length=1000)
    # Nombre propio (opcional, máx. 80). La descripción original queda como está.
    titulo: Optional[str] = Field(default=None, max_length=80)
    recordar_titulo: bool = False
    # Si ya tienes ese gasto registrado por otro canal (atajo, correo, extracto) la app avisa (409)
    # en vez de duplicarlo; con true se guarda de todos modos («es otro gasto igual»).
    confirmar_nuevo: bool = False


class MovimientoUpdate(BaseModel):
    """Todos los campos son opcionales: solo se cambia lo que se envía."""
    cuenta_id: Optional[str] = None
    descripcion: Optional[str] = Field(default=None, max_length=300)
    monto: Optional[float] = Field(default=None, gt=0)
    tipo: Optional[Literal["income", "expense", "transfer"]] = None
    categoria: Optional[str] = Field(default=None, max_length=60)
    # "" = quitar la subcategoría. Si cambia la categoría y no se envía, la subcategoría se limpia.
    subcategoria: Optional[str] = Field(default=None, max_length=40)
    fecha: Optional[datetime] = None
    notas: Optional[str] = Field(default=None, max_length=1000)
    # Nombre propio: "" lo quita (vuelve el texto del banco). Máx. 80.
    titulo: Optional[str] = Field(default=None, max_length=80)
    recordar_titulo: bool = False


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
    titulo: Optional[str] = None
    categoria: str
    subcategoria: Optional[str] = None
    tipo: str
    monto: float
    fuente: str
    notas: str
    cat_origen: Optional[str] = None
    cat_confirmada: Optional[bool] = True
    # ¿Espera categoría? Lo decide el servidor (app/pendientes.py); None = esta respuesta no lo calculó.
    por_categorizar: Optional[bool] = None
    # Por dónde llegó (manual | atajo | correo | extracto | importacion) y qué canales lo confirmaron
    # (insignia «Registrado desde...»). Opcionales: los movimientos viejos pueden no traerlos.
    origen: Optional[str] = None
    canales: Optional[list[str]] = None
    conciliado_en: Optional[datetime] = None

    class Config:
        from_attributes = True


class RecategorizarComercioRequest(BaseModel):
    categoria: str = Field(min_length=1)
    patron: Optional[str] = Field(default=None, max_length=60)  # si no viene, se deduce de la descripción
    aplicar_a_todos: bool = True
    subcategoria: Optional[str] = Field(default=None, max_length=40)
    confirmar_peligrosa: bool = False  # guardar aunque la huella sea muy corta o genérica


class ConfirmarCategoriasRequest(BaseModel):
    movimiento_ids: Optional[list[str]] = None  # None = todos los pendientes de revisión


class MovimientoRapidoCreate(BaseModel):
    """Para registro sin login: Atajos de iOS (disparador 'Transacción' de Wallet),
    Tasker, reglas de correo. Acepta lo que entrega iOS tal cual: comercio, monto
    (número o texto colombiano como '45.000,00'), tarjeta, fecha y moneda."""
    monto: float = Field(gt=0)
    tipo: Literal["income", "expense"] = "expense"
    descripcion: Optional[str] = Field(default=None, max_length=150)  # si falta, se usa el comercio
    comercio: Optional[str] = Field(default=None, max_length=150)
    tarjeta: Optional[str] = Field(default=None, max_length=120)  # nombre de la tarjeta en Wallet
    cuenta: Optional[str] = None  # nombre de cuenta a buscar (ej. "Nequi"); si no hay match usa la primera del usuario
    fecha: Optional[str] = None  # ISO o dd/mm/aaaa; si no se entiende se usa la hora actual
    moneda: Optional[str] = Field(default=None, max_length=5)
    fuente: str = Field(default="shortcut", max_length=30)  # shortcut | wallet | sms | email
    # Opcional: identificador único de la transacción (si el Atajo lo tiene). Un reintento con el mismo id
    # jamás crea otro movimiento, sin importar cuánto tiempo pase.
    id_transaccion: Optional[str] = Field(default=None, max_length=80)

    @model_validator(mode="before")
    @classmethod
    def _normalizar(cls, datos):
        if not isinstance(datos, dict):
            return datos
        from app.wallet import parse_monto_co

        # Las claves llegan como las escribió quien armó el Atajo ("Comercio", "Monto"...):
        # se pasan a minúsculas para no depender de eso.
        d = {str(k).strip().lower(): v for k, v in datos.items()}
        # Nombres que usa iOS (en inglés y en español) y variantes del Atajo.
        for original, destino in (("comerciante", "comercio"), ("importe", "monto"), ("cantidad", "monto"),
                                  ("tarjeta_o_pase", "tarjeta"), ("tarjeta o pase", "tarjeta"),
                                  ("merchant", "comercio"), ("amount", "monto"), ("card", "tarjeta"),
                                  ("nombre_tarjeta", "tarjeta"), ("tarjeta_nombre", "tarjeta"),
                                  ("date", "fecha"), ("currency", "moneda"), ("name", "descripcion")):
            if d.get(destino) in (None, "") and d.get(original) not in (None, ""):
                d[destino] = d[original]
        d["monto"] = parse_monto_co(d.get("monto"))
        for campo in ("descripcion", "comercio", "tarjeta", "cuenta", "moneda", "fecha"):
            v = d.get(campo)
            d[campo] = str(v).strip()[:150] if v not in (None, "") and str(v).strip() else None
        import re
        fuente = re.sub(r"[\s-]+", "_", str(d.get("fuente") or "shortcut").strip().lower())[:30]
        d["fuente"] = fuente
        # Al cerrar la app del banco el Atajo manda la nota (opcional): sin ella el
        # backend pone 'Movimiento en <cuenta>'. En cualquier otra fuente sí se exige.
        if fuente != "cierre_app" and not d.get("descripcion") and not d.get("comercio"):
            raise ValueError("Falta el comercio o la descripción del movimiento")
        tipo = str(d.get("tipo") or "expense").strip().lower()
        d["tipo"] = {"gasto": "expense", "egreso": "expense", "ingreso": "income"}.get(tipo, tipo)
        return d


class MovimientoRapidoOut(MovimientoOut):
    """Respuesta corta para que el Atajo muestre una notificación local."""
    mensaje: str
    duplicado: bool = False
    por_confirmar: bool = False
    cuenta_nombre: Optional[str] = None
    ya_estaba_por: Optional[str] = None  # canal por el que ya estaba registrado ('correo', 'extracto', 'manual'...)


class RecategorizarMasivoRequest(BaseModel):
    movimiento_ids: list[str]
    categoria: str
    subcategoria: Optional[str] = Field(default=None, max_length=40)


class RecategorizarMasivoResponse(BaseModel):
    ok: bool
    actualizados: int


class MoverMasivoRequest(BaseModel):
    movimiento_ids: list[str] = Field(min_length=1, max_length=500)
    cuenta_id: str


class EliminarMasivoRequest(BaseModel):
    # Por qué se borra (ver app/duplicados.registrar_borrado): duplicado | error | no_va
    motivo: str = Field(default="duplicado", pattern="^(duplicado|error|no_va)$")
    movimiento_ids: list[str] = Field(min_length=1, max_length=500)


class MasivoResponse(BaseModel):
    ok: bool
    actualizados: int = 0
    omitidos: int = 0


class MovimientoPorVozCreate(BaseModel):
    """Para registro por voz/Siri: se manda la frase dicha tal cual, sin
    estructurar. El backend interpreta monto/tipo/descripción."""
    texto: str
    cuenta: Optional[str] = None
    tarjeta: Optional[str] = Field(default=None, max_length=120)


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
    patron: str = Field(min_length=1, max_length=100)
    categoria: str = Field(max_length=60)
    subcategoria: Optional[str] = Field(default=None, max_length=40)
    tipo: Optional[str] = None
    prioridad: int = 0


class AprenderReglaRequest(BaseModel):
    descripcion: str = Field(min_length=1, max_length=200)  # de ahí se saca la huella del comercio
    categoria: str = Field(min_length=1, max_length=60)
    subcategoria: Optional[str] = Field(default=None, max_length=40)
    tipo: Optional[str] = None
    aplicar_anteriores: bool = False
    confirmar_peligrosa: bool = False


class ReglaCategoriaOut(BaseModel):
    id: str
    patron: str
    categoria: str
    subcategoria: Optional[str] = None
    tipo: Optional[str]
    prioridad: int
    activa: Optional[bool] = True  # False = en pausa (no se aplica)

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
    categoria: str = Field(max_length=60)
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
    moneda_base: str = "COP"
    monedas_sin_tasa: list[str] = []


class EnMiBolsillo(BaseModel):
    """'In My Pocket': cuánto es realmente tuyo para gastar, después de
    descontar compromisos ya conocidos (recurrentes pendientes y aportes
    a metas), no solo el saldo crudo de las cuentas."""
    saldo_total: float
    recurrentes_pendientes_mes: float
    aportes_comprometidos_mes: float
    # Cuotas de compras a cuotas con tarjeta que vencen este mes. La deuda de la tarjeta
    # ya está restada en el saldo, así que solo se descuenta de disponible_real si se pide.
    cuotas_tarjeta_mes: float = 0
    disponible_real: float
    disponible_real_por_dia: float
    dias_restantes_mes: int
    moneda_base: str = "COP"  # los montos de arriba vienen en esta moneda
    monedas_sin_tasa: list[str] = []  # cuentas en estas monedas NO están sumadas


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
    num_movimientos: int = 0


class Proyeccion(BaseModel):
    gasto_proyectado_mes: float
    dias_transcurridos: int
    dias_restantes_mes: int
    ritmo_diario: float


class TendenciasResponse(BaseModel):
    meses: list[TendenciaMes]
    proyeccion: Proyeccion
    moneda_base: str = "COP"
    monedas_sin_tasa: list[str] = []


class FlujoCajaMes(BaseModel):
    mes: str
    saldo_proyectado: float
    ingresos_esperados: float
    gastos_esperados: float
    cuotas_tarjeta: float = 0  # cuotas de compras diferidas que vencen ese mes (informativo)


class FlujoCajaFuturo(BaseModel):
    saldo_actual: float
    meses: list[FlujoCajaMes]
    moneda_base: str = "COP"
    monedas_sin_tasa: list[str] = []


class ReporteMensual(BaseModel):
    mes: str
    ingresos: float
    gastos: float
    ahorro: float
    tasa_ahorro: float
    top_categorias: list[dict]
    salud: dict
    moneda_base: str = "COP"
    monedas_sin_tasa: list[str] = []


# ── Metas de ahorro ──────────────────────────────────────

class MetaCreate(BaseModel):
    nombre: str = Field(max_length=80)
    descripcion: Optional[str] = Field(default="", max_length=500)
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
    nombre: str = Field(max_length=80)
    monto: float = Field(gt=0)
    tipo: str = "expense"
    categoria: str = Field(default="Otros", max_length=60)
    cuenta_id: Optional[str] = None
    dia_del_mes: int = Field(default=1, ge=1, le=31)
    alerta_dias_antes: int = 2
    notas: Optional[str] = Field(default="", max_length=500)


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
    nombre: str = Field(max_length=80)
    tipo: str = "credito"
    entidad: Optional[str] = Field(default="", max_length=80)
    saldo_inicial: float
    saldo_actual: Optional[float] = None
    tasa_mensual: float = 0
    cuota_mensual: float = 0
    fecha_fin: Optional[datetime] = None
    dia_corte: Optional[int] = None
    dia_pago: int = 1
    cuenta_pago_id: Optional[str] = None
    notas: Optional[str] = Field(default="", max_length=500)


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
    # La app de Google aún no está verificada: solo entran correos agregados como 'test user'.
    modo_pruebas: bool = False
    soporte_email: str = ""
    # ¿Ya dio la autorización específica de lectura de correo?
    consentimiento: bool = True
    # Los dos usos del correo, cada uno con su interruptor (activos por defecto).
    leer_movimientos: bool = True
    leer_extractos: bool = True


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
    # Calculados al leer, en hora de Colombia (sin zona, listos para mostrar): la fecha del MOVIMIENTO que
    # se usará al aprobar (la del texto del correo o, si no trae, la de recepción) y cuándo llegó el correo.
    fecha_movimiento: Optional[datetime] = None
    fecha_movimiento_con_hora: bool = False
    fecha_del_texto: bool = False  # True: el banco la escribió en el correo; False: es la de recepción
    recibido_en_co: Optional[datetime] = None
    # Solo en estado 'ya_registrado': el movimiento que ya existía {descripcion, monto, fecha, canales}.
    registrado_como: Optional[dict] = None
    # Calculados al leer (no son columnas): quién envió el correo y qué cuenta le corresponde.
    banco_detectado: Optional[str] = None
    cuenta_sugerida_id: Optional[str] = None
    falta_cuenta: bool = False
    # El banco tiene varias cuentas (p. ej. ahorros y tarjeta) y no hay cómo saber cuál: se pregunta.
    cuentas_candidatas: list[str] = []
    pregunta_cuenta: Optional[str] = None
    producto_detectado: Optional[str] = None  # credito | debito | None
    # El monto no se pudo leer del correo (<= 0): hay que pedirlo antes de aprobar.
    falta_monto: bool = False
    # Solo en 'descartado'/'ignorado': por qué no está en «Por revisar», dicho con palabras de la persona.
    motivo_descarte: Optional[str] = None
    # Por qué se sugirió esa categoría ('por tu regla «rappi»'); None si la eligió el usuario
    # o no se pudo decidir. `preguntar_categoria`: quedó en 'Otros', hay que preguntarle.
    razon_categoria: Optional[str] = None
    preguntar_categoria: bool = False
    # Solo al aprobar/editar con 'Recordar': qué pasó con la regla del comercio.
    regla_guardada: Optional[bool] = None
    regla_omitida: Optional[str] = None
    anteriores_actualizados: Optional[int] = None

    class Config:
        from_attributes = True


class CorreoGastoUpdate(BaseModel):
    monto: Optional[float] = None
    comercio: Optional[str] = None
    categoria: Optional[str] = None
    tipo: Optional[str] = None
    # Con categoría nueva: guarda la regla del comercio (y, opcional, recategoriza los anteriores).
    recordar: bool = False
    aplicar_anteriores: bool = False


class AprobarCorreoRequest(BaseModel):
    # Opcional a propósito: sin cuenta elegida se responde 400 claro en vez de 422.
    cuenta_id: Optional[str] = None
    # Monto escrito por el usuario cuando el correo no lo traía (debe ser > 0).
    monto: Optional[float] = None
    # Categoría elegida por el usuario al aprobar (si cambió la sugerida).
    categoria: Optional[str] = None
    recordar: bool = False
    aplicar_anteriores: bool = False
    # Fecha del movimiento corregida por la persona (hora de Colombia). Sin ella se usa la leída del correo.
    fecha: Optional[datetime] = None
    # Nombre propio para el movimiento que se crea (la descripción del banco queda intacta).
    titulo: Optional[str] = Field(default=None, max_length=80)
    recordar_titulo: bool = False


class LecturaCorreoRequest(BaseModel):
    leer_movimientos: Optional[bool] = None
    leer_extractos: Optional[bool] = None


class SincronizarCorreosResponse(BaseModel):
    ok: bool
    nuevos: int
    omitidos: int
    extractos_nuevos: int = 0
    error: Optional[str] = None
    # Progreso de la sincronización por lotes: el cliente repite la llamada
    # mientras `completado` sea False. Los contadores son de toda la corrida.
    leidos: int = 0
    total_estimado: int = 0
    pendientes: int = 0
    completado: bool = True
    extractos_encontrados: int = 0
    # Carriles independientes (se AÑADEN; los campos de arriba siguen igual).
    tipo: str = "todo"
    aviso: Optional[str] = None
    movimientos_leidos: int = 0
    movimientos_ya_registrados: int = 0
    extractos_leidos: int = 0


class ExtractoCorreoOut(BaseModel):
    id: str
    remitente: str
    asunto: str
    archivo: str
    banco: str
    periodo: str
    cuenta_sugerida_id: Optional[str]
    estado: str
    historial_id: Optional[str]
    recibido_en: Optional[datetime]
    # Solo en extractos procesados: movimientos que se cruzaron (exactos + aproximados).
    cruzados: Optional[int] = None
    # Banco con varias cuentas sin ganador claro: ids posibles y la pregunta en lenguaje simple.
    cuentas_candidatas: list[str] = []
    pregunta_cuenta: Optional[str] = None
    # Solo si pide clave (o ya se abrió con ella): 'abrio' | 'no_abrio' | 'por_probar' | 'sin_clave'.
    clave_estado: Optional[str] = None
    # Solo tarjeta: lo que decía el CUERPO del aviso (pago_minimo, periodo_facturado, fecha_corte, fecha_limite).
    datos_cuerpo: Optional[dict] = None

    @field_validator("datos_cuerpo", mode="before")
    @classmethod
    def _datos_cuerpo_json(cls, v):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                return None
        return v if isinstance(v, dict) else None

    class Config:
        from_attributes = True


class FijarMesIn(BaseModel):
    mes: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")  # AAAA-MM


class ClavePdfIn(BaseModel):
    clave: str = Field(min_length=1, max_length=120)


class ProbarClaveIn(BaseModel):
    extracto_id: Optional[str] = None  # sin id: se prueba en todos los extractos que piden clave


class ConciliarExtractoRequest(BaseModel):
    cuenta_id: str


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
    moneda_base: str = "COP"
    monedas_sin_tasa: list[str] = []


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
    desde: str | None = None
    hasta: str | None = None
    moneda_base: str = "COP"
    monedas_sin_tasa: list[str] = []
    etiqueta: str | None = None


class PreguntarRequest(BaseModel):
    pregunta: str = Field(min_length=1, max_length=500)


class PreguntarResponse(BaseModel):
    respuesta: str
    fuentes: list[str] = []
    sugerencias: list[str] = []


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
    estado: str  # exacto | aproximado | faltante | completado | sobrante | importado
    match_id: Optional[str] = None
    categoria_sugerida: Optional[str] = None
    descripcion_registrada: Optional[str] = None  # completado: lo que había registrado el usuario
    monto_registrado: Optional[float] = None  # completado: monto registrado (puede diferir del banco)
    razon_categoria: Optional[str] = None  # por qué se sugiere esa categoría
    confianza_categoria: Optional[float] = None  # 0..1: qué tan segura está la sugerencia (None = sin sugerencia)
    auto: bool = False  # importado solo (ajuste "importar lo que reconozco"): se puede deshacer
    movimiento_id: Optional[str] = None  # id del movimiento creado al auto-importar
    pista: Optional[str] = None  # 'posible_traslado_propio': la contraparte parece el titular; mueve saldo igual
    fecha_registrada: Optional[str] = None  # aproximado: fecha del movimiento que ya tenías (para verlos lado a lado)
    duplicado_evitado: bool = False  # otro canal (correo, atajo, a mano) ya lo había registrado: se juntó, no se repitió
    # Línea con varios montos: el lector no sabe cuál es el correcto. No se importa hasta que la persona elige.
    lectura_dudosa: bool = False
    montos_alternativos: Optional[list[float]] = None  # los montos que aparecen escritos en la línea
    pago_tarjeta: bool = False  # «Pago ...» de un extracto de tarjeta: se sugiere como traslado entre tus cuentas
    # Pago de la tarjeta: monto A y cómo se aplicó (capital / intereses / cargos y los dos montos B y C del extracto).
    pago_detalle: Optional[dict] = None  # {capital, intereses, cargos, aplicado: [B, C]}
    linea_tipo: Optional[str] = None  # compra | compra_en_cuotas | cuota_manejo | pago | comision (extracto de tarjeta)
    cuotas: Optional[str] = None  # «N de M»
    restante: Optional[float] = None  # lo que falta por pagar de una compra en cuotas
    aviso_linea: Optional[str] = None  # texto para la persona cuando el lector no tiene certeza
    marcar_por_defecto: Optional[bool] = None  # False = la casilla queda apagada hasta que la persona confirme
    rendimiento: bool = False  # «Rendimientos de tu cuenta ...»: ingreso real que el extracto resume pero no lista
    categoria_fija: Optional[str] = None  # categoría de sistema que la línea ya trae (p. ej. «Rendimientos»)


class ProcesarExtractoResponse(BaseModel):
    ok: bool
    # Extracto de la tarjeta de Nu: resumen de la página 1 y si lo leído suma lo que dice el extracto.
    resumen_tarjeta: Optional[dict] = None
    verificacion: Optional[list[dict]] = None
    lectura_completa: Optional[bool] = None
    lineas_leidas: Optional[int] = None
    mensaje_lectura: Optional[str] = None
    historial_id: Optional[str] = None
    cuenta_id: Optional[str] = None  # cuenta del extracto (al reabrir una revisión desde el historial)
    banco_detectado: Optional[str] = None
    total_movimientos: int = 0
    exactos: int = 0
    aproximados: int = 0
    faltantes: int = 0
    descartados: int = 0
    anteriores: int = 0  # líneas anteriores a la fecha de inicio (punto de partida): no se ofrecen
    review: list[MovimientoReview] = []
    error: Optional[str] = None
    auto_importados: int = 0  # movimientos que entraron solos (solo con el ajuste activo; quedan "por revisar")
    ya_registrados: int = 0  # exactos + aproximados + completados; ya_registrados + faltantes + auto_importados = total_movimientos
    autoimportar_activo: bool = False  # el ajuste 'importar solo lo que reconozco con certeza'
    completados: int = 0  # movimientos rápidos completados con los datos del banco
    sobrantes: int = 0  # registrados en el periodo que no aparecen en el extracto
    borrados_antes: int = 0  # líneas que coinciden con un movimiento que borraste: no se vuelven a crear
    periodo_desde: Optional[str] = None  # ISO, primer movimiento del extracto
    periodo_hasta: Optional[str] = None
    parece_extracto: bool = True  # False: el archivo no parece un extracto (carta, factura...); no se importa nada
    motivo_rechazo: Optional[str] = None
    motivo_error: Optional[str] = None  # código (extractos_vista.MOTIVOS) si el archivo no se pudo leer
    requiere_clave: bool = False  # el PDF está protegido y falta (o es incorrecta) la clave
    # Aviso (no bloquea): ese mes de esa cuenta ya estaba conciliado antes de subir este archivo.
    ya_conciliado: Optional[dict] = None  # {"mes": "2026-09", "cruzados": n}
    # Solo si la cuenta es una tarjeta de crédito y el extracto trae datos legibles:
    # {cambios, datos, texto}. Es una PROPUESTA: se aplica solo si el cliente pulsa 'Aplicar'.
    propuesta_tarjeta: Optional[dict] = None
    # Aviso (no bloquea): el extracto parece de otro producto del mismo banco (tarjeta vs ahorros).
    aviso_cuenta: Optional[str] = None
    # Qué pasó con cada línea leída (modelo único de app/estado_traer.py): leidas, ya_estaban,
    # nuevas_agregadas, por_revisar, descartadas, anteriores, duplicadas_detectadas, dudosas.
    conteo: Optional[dict] = None
    # Lo que el extracto dice de saldos (para cuadrar): {saldo_inicial, saldo_final, fecha_corte,
    # periodo_inicio, moneda, origen, cadena_ok, pago_minimo}; None si el extracto no trae saldos legibles.
    saldos_extracto: Optional[dict] = None
    # Solo al reabrir una revisión: de dónde salió el extracto y a qué cuenta quedó
    # {titulo, origen_texto, asunto, archivo, cuenta_id, cuenta_nombre, mes_etiqueta}.
    origen: Optional[dict] = None


class ResolverDudososRequest(BaseModel):
    mismos: list[str] = []  # huellas de líneas que SON el mismo gasto que ya tenías: se juntan
    distintos: list[str] = []  # huellas de líneas que son OTRO gasto: quedan para agregar


class ImportarFaltantesRequest(BaseModel):
    fingerprints: list[str]
    categorias: Optional[dict[str, str]] = None  # fingerprint -> categoría elegida por el usuario, si la cambió
    recordar: list[str] = []  # fingerprints cuya categoría elegida se guarda como regla del comercio
    aplicar_anteriores: list[str] = []  # subconjunto de `recordar`: además recategoriza movimientos pasados
    titulos: Optional[dict[str, str]] = None  # fingerprint -> nombre propio (máx. 80); "" = el original
    recordar_titulo: list[str] = []  # fingerprints cuyo nombre se recuerda para ese comercio
    montos: Optional[dict[str, float]] = None  # fingerprint -> monto elegido (obligatorio en líneas de lectura dudosa)


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
    saldo_inicial_extracto: Optional[float] = None
    saldo_final_extracto: Optional[float] = None
    fecha_corte: Optional[str] = None
    moneda: Optional[str] = None
    cuadre_estado: Optional[str] = None
    cuadre_diferencia: Optional[float] = None
    lectura_completa: Optional[bool] = None  # tarjeta de Nu: ¿lo leído suma lo que dice el extracto?
    mensaje_lectura: Optional[str] = None  # «Leí 17 líneas y suman lo que dice tu extracto ✓»

    class Config:
        from_attributes = True


# ── Estrategia de deudas ────────────────────────

class PlanDeudaOut(BaseModel):
    id: str
    nombre: str
    mes_libre: Optional[int]  # mes (1 = el próximo) en que queda en cero


class ResultadoMetodoOut(BaseModel):
    metodo: str  # sin_extra | avalancha | bola_de_nieve
    meses: Optional[int]  # None si no se termina de pagar en el horizonte
    fecha_libre: Optional[str]  # YYYY-MM
    intereses_totales: float
    ahorro_intereses: Optional[float]  # frente a pagar solo las cuotas actuales
    meses_ahorrados: Optional[int]
    orden: list[PlanDeudaOut]
    saldo_por_mes: list[float]  # deuda total al cierre de cada mes (0 = hoy)


class EstrategiaOut(BaseModel):
    extra_mensual: float
    deuda_total: float
    sin_extra: ResultadoMetodoOut
    avalancha: ResultadoMetodoOut
    bola_de_nieve: ResultadoMetodoOut
    mejor: str  # avalancha | bola_de_nieve
