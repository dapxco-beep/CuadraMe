import secrets
import uuid
from datetime import datetime

from sqlalchemy.orm import deferred
from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer, Index, UniqueConstraint

from app.database import Base
from app.utiles import ahora_co


def gen_uuid():
    return str(uuid.uuid4())


def gen_api_key():
    return "cdm_" + secrets.token_urlsafe(24)


class Perfil(Base):
    __tablename__ = "perfiles"

    usuario_id = Column(String, primary_key=True)  # UUID de Supabase Auth
    plan = Column(String, default="free")  # free | pro
    stripe_customer_id = Column(String, nullable=True)
    # Clave en claro: SOLO de perfiles antiguos aún no migrados. Las claves nuevas se
    # guardan como hash (ver app/claves_api.py) y esta columna queda en NULL.
    api_key = Column(String, unique=True, index=True, nullable=True)
    # `deferred`: no entra en los SELECT de Perfil, así la app arranca aunque la columna
    # aún no exista en la base (script supabase/migraciones/api_key_hash.sql).
    api_key_hash = deferred(Column(String, unique=True, index=True, nullable=True))
    api_key_prefijo = deferred(Column(String, nullable=True))
    gmail_conectado = Column(Boolean, default=False)
    gmail_refresh_token_enc = Column(String, nullable=True)  # cifrado con Fernet
    gmail_email = Column(String, nullable=True)
    gmail_etiqueta = Column(String, default="gastos")
    confianza_autoimport = Column(Float, default=0.75)  # 0.5-0.95: qué tan segura debe estar la categorización antes de auto-importar un movimiento sin preguntar
    # Importar solos, al subir un extracto, los movimientos que la app categoriza con certeza
    # (umbral = confianza_autoimport). Apagado por defecto: nada se importa sin que el usuario confirme.
    autoimportar_extractos = Column(Boolean, default=False)
    # Recordatorio nocturno (8pm Colombia) si hoy no registró nada; opcional.
    recordatorio_diario = Column(Boolean, default=False)
    ultimo_recordatorio = Column(String, nullable=True)  # YYYY-MM-DD del último aviso, para no repetir
    # Última vez que alguien usó la API key (Atajo de iPhone, Tasker...): alimenta el semáforo de "Conexiones".
    api_key_ultimo_uso = Column(DateTime, nullable=True)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Cuándo se creó el perfil (= primer uso): alimenta la tendencia de usuarios de «Salud del negocio».
    # Los perfiles anteriores quedan en NULL y se estiman con su primer movimiento.
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=True)


class Cuenta(Base):
    __tablename__ = "cuentas"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)  # UUID de Supabase Auth
    nombre = Column(String, nullable=False)
    tipo = Column(String, default="ahorro")  # ahorro | efectivo | credito | inversion
    saldo = Column(Float, default=0)
    moneda = Column(String, default="COP")
    icono = Column(String, default="🏦")
    # Solo para tipo "credito" (tarjeta de crédito). Todos opcionales: una
    # cuenta de crédito sin cupo sigue funcionando como una cuenta más.
    cupo_total = Column(Float, nullable=True)
    dia_corte = Column(Integer, nullable=True)  # 1-31
    dia_pago = Column(Integer, nullable=True)  # 1-31
    tasa_ea = Column(Float, nullable=True)  # tasa efectiva anual en %
    ultima_alerta_pago = Column(String, nullable=True)  # fecha de pago ya avisada (YYYY-MM-DD)
    # Cómo se llama esta cuenta/tarjeta en Apple Wallet ("Visa Bancolombia, 1234").
    # Varios alias separados por coma; el pago con el celular se asigna por coincidencia parcial.
    alias_tarjeta = Column(String, nullable=True)


class CuentaCompartida(Base):
    __tablename__ = "cuentas_compartidas"

    id = Column(String, primary_key=True, default=gen_uuid)
    cuenta_id = Column(String, nullable=False, index=True)
    usuario_id = Column(String, nullable=False, index=True)  # a quién se le compartió
    rol = Column(String, default="viewer")  # viewer | editor
    creado_en = Column(DateTime, default=datetime.utcnow)


class InvitacionCuenta(Base):
    __tablename__ = "invitaciones_cuenta"

    id = Column(String, primary_key=True, default=gen_uuid)
    cuenta_id = Column(String, nullable=False, index=True)
    invitado_por = Column(String, nullable=False)  # usuario_id de quien invita
    email_invitado = Column(String, nullable=False, index=True)
    rol = Column(String, default="viewer")
    estado = Column(String, default="pendiente")  # pendiente | aceptada | rechazada
    creado_en = Column(DateTime, default=datetime.utcnow)


class RachaUsuario(Base):
    """Racha de días consecutivos registrando al menos un movimiento.
    Base para otorgar vidas del ahorcado por constancia."""
    __tablename__ = "rachas_usuario"

    usuario_id = Column(String, primary_key=True)
    dias_consecutivos = Column(Integer, default=0)
    ultimo_dia_activo = Column(DateTime, nullable=True)
    mejor_racha = Column(Integer, default=0)


class VidaAhorcado(Base):
    """Créditos de juego ganados por logros financieros reales (presupuesto
    cumplido, meta alcanzada, racha de constancia). Se consumen al jugar."""
    __tablename__ = "vidas_ahorcado"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    origen = Column(String, nullable=False)  # racha_7 | racha_30 | presupuesto_cumplido | meta_cumplida
    usada = Column(Boolean, default=False)
    creado_en = Column(DateTime, default=datetime.utcnow)


class PartidaAhorcado(Base):
    __tablename__ = "partidas_ahorcado"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    palabra = Column(String, nullable=False)
    pista = Column(String, default="")
    letras_intentadas = Column(String, default="")  # letras separadas por coma
    intentos_restantes = Column(Integer, default=6)
    estado = Column(String, default="jugando")  # jugando | ganada | perdida
    creado_en = Column(DateTime, default=datetime.utcnow)


class ReglaCategoria(Base):
    __tablename__ = "reglas_categoria"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    patron = Column(String, nullable=False)  # texto a buscar en la descripción (contiene, case-insensitive)
    categoria = Column(String, nullable=False)
    tipo = Column(String, nullable=True)  # income | expense | transfer | null (no forzar tipo)
    prioridad = Column(Integer, default=0)  # reglas con mayor prioridad se evalúan primero
    creado_en = Column(DateTime, default=datetime.utcnow)


class Movimiento(Base):
    __tablename__ = "movimientos"
    __table_args__ = (
        # Casi toda consulta filtra por cuenta o por usuario Y por rango de fechas (ver supabase/migraciones/indices_rendimiento.sql).
        Index("ix_movimientos_cuenta_fecha", "cuenta_id", "fecha"),
        Index("ix_movimientos_usuario_fecha", "usuario_id", "fecha"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    cuenta_id = Column(String, index=True, nullable=False)
    fecha = Column(DateTime, default=ahora_co, index=True)  # hora Colombia (naive), no UTC
    descripcion = Column(String, nullable=False)
    categoria = Column(String, default="Otros")
    tipo = Column(String, nullable=False)  # income | expense | transfer
    monto = Column(Float, nullable=False)
    fuente = Column(String, default="manual")  # manual | csv_import | ai | sms
    notas = Column(String, default="")
    # Categorización automática transparente: si la app puso la categoría sola
    # queda cat_confirmada=False y cat_origen dice por qué (regla | comercio |
    # similar | sugerida). Lo que escribe el usuario nace confirmado.
    cat_origen = Column(String, nullable=True)
    cat_confirmada = Column(Boolean, default=True)
    # Cruce con el extracto: un movimiento rápido (Wallet, cierre de app...) se
    # completa con los datos del banco y queda conciliado (no se vuelve a tocar).
    conciliado_en = Column(DateTime, nullable=True)
    extracto_id = Column(String, nullable=True)
    # Deduplicación entre canales (app/duplicados.py). Ambas opcionales: los movimientos
    # viejos no las tienen y se deducen de `fuente` (ver duplicados.origen_de_movimiento).
    #   origen: manual | atajo | correo | extracto | importacion  (por dónde NACIÓ el movimiento)
    #   huella_externa: identificador del canal de origen (id del mensaje de Gmail, huella de la
    #                   línea del extracto, id de transacción o huella del disparo del atajo).
    origen = Column(String, nullable=True)
    huella_externa = Column(String, nullable=True)


class HuellaOrigen(Base):
    """Un canal que confirmó (o descartó) un movimiento: «el correo X», «la línea Y del extracto».

    Sirve para tres cosas: 1) un reintento o re-sincronización del MISMO canal nunca duplica
    (la huella ya existe); 2) saber por qué canales llegó un movimiento (insignia «Registrado
    desde: atajo + correo»); 3) recordar lo que el usuario borró: al borrar un movimiento sus
    filas pasan a 'descartado' (con una foto de cuenta/tipo/monto/fecha) y el correo o extracto
    equivalente que llegue después NO resucita el movimiento."""
    __tablename__ = "huellas_origen"
    __table_args__ = (
        Index("ix_huellas_usuario_huella", "usuario_id", "huella"),
        Index("ix_huellas_movimiento", "movimiento_id"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    movimiento_id = Column(String, nullable=True)
    huella = Column(String, nullable=False)
    origen = Column(String, nullable=False)
    estado = Column(String, default="vigente")  # vigente | descartado | no_duplicado
    # Foto del movimiento (para reconocer, ya borrado, el correo/extracto que llegue después).
    cuenta_id = Column(String, nullable=True)
    tipo = Column(String, nullable=True)
    monto = Column(Float, nullable=True)
    fecha = Column(DateTime, nullable=True)
    clave = Column(String, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


class Presupuesto(Base):
    __tablename__ = "presupuestos"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    categoria = Column(String, nullable=False)
    periodo = Column(String, default="monthly")
    limite = Column(Float, nullable=False)
    alerta_pct = Column(Integer, default=80)
    # Envelope budgeting: plata movida manualmente hacia (positivo) o desde
    # (negativo) esta categoría, además de su límite mensual — así lo que
    # sobra en una categoría se puede "pasar" a otra que se quedó corta,
    # en vez de que el sobrante simplemente desaparezca cada mes.
    sobre_ajuste = Column(Float, default=0)
    ultima_alerta_mes = Column(String, nullable=True)  # "YYYY-MM" del último aviso push de umbral, para no repetirlo a diario
    activo = Column(Boolean, default=True)


class Meta(Base):
    __tablename__ = "metas"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    descripcion = Column(String, default="")
    monto_objetivo = Column(Float, nullable=False)
    monto_actual = Column(Float, default=0)
    icono = Column(String, default="🎯")
    fecha_inicio = Column(DateTime, default=datetime.utcnow)
    fecha_objetivo = Column(DateTime, nullable=True)
    aporte_automatico = Column(Float, nullable=True)  # si tiene valor, se aporta este monto cada mes
    dia_aporte = Column(Integer, default=1)
    cuenta_origen_id = Column(String, nullable=True)  # de dónde sale la plata del aporte automático
    ultimo_aporte_automatico = Column(DateTime, nullable=True)
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
    ultima_notificacion_vencimiento = Column(DateTime, nullable=True)
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


class CorreoGasto(Base):
    __tablename__ = "correos_gastos"
    __table_args__ = (Index("ix_correos_gastos_usuario_estado", "usuario_id", "estado"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    gmail_msg_id = Column(String, nullable=False, index=True)
    remitente = Column(String, default="")
    asunto = Column(String, default="")
    snippet = Column(String, default="")
    recibido_en = Column(DateTime, nullable=True)
    monto = Column(Float, default=0)
    moneda = Column(String, default="COP")
    comercio = Column(String, default="")
    categoria_sugerida = Column(String, default="Otros")
    tipo_sugerido = Column(String, default="expense")  # income | expense (antes también transfer)
    confianza = Column(Float, default=0)
    estado = Column(String, default="pendiente")  # pendiente | aprobado | descartado
    movimiento_id = Column(String, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


class ExtractoCorreo(Base):
    """Extracto bancario (PDF adjunto) detectado en el Gmail del usuario.
    NO guarda el PDF: solo metadatos. Para conciliar se vuelve a descargar."""
    __tablename__ = "extractos_correo"
    __table_args__ = (
        UniqueConstraint("usuario_id", "gmail_msg_id", "archivo", name="uq_extracto_correo"),
        Index("ix_extractos_correo_usuario_estado", "usuario_id", "estado"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    gmail_msg_id = Column(String, nullable=False)
    archivo = Column(String, default="")  # nombre del adjunto
    remitente = Column(String, default="")
    asunto = Column(String, default="")
    banco = Column(String, default="")
    periodo = Column(String, default="")
    cuenta_sugerida_id = Column(String, nullable=True)
    estado = Column(String, default="nuevo")  # nuevo | falta_clave | procesado | descartado | error
    historial_id = Column(String, nullable=True)
    recibido_en = Column(DateTime, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


class SyncGmail(Base):
    """Estado de la sincronización de Gmail por usuario. Permite hacerla por
    lotes (cada request lee pocos correos para no pasar el timeout) y retomarla
    donde quedó. Los campos `cursor_*` solo valen mientras `en_curso` es True."""
    __tablename__ = "sync_gmail"

    usuario_id = Column(String, primary_key=True)
    en_curso = Column(Boolean, default=False)
    fase = Column(String, default="etiqueta")  # etiqueta | notificaciones | extractos
    fase_iniciada = Column(Boolean, default=False)  # ya se pidió la primera página de la fase
    cursor_token = Column(String, nullable=True)  # nextPageToken de Gmail para la siguiente página
    cursor_ids = Column(String, default="[]")  # JSON: ids de la página actual que faltan por leer
    reintento_clave_hecho = Column(Boolean, default=False)
    desde = Column(DateTime, nullable=True)  # inicio de la ventana de búsqueda de esta corrida
    iniciada_en = Column(DateTime, nullable=True)
    # Contadores de la corrida en curso.
    leidos = Column(Integer, default=0)
    total_estimado = Column(Integer, default=0)
    nuevos = Column(Integer, default=0)
    omitidos = Column(Integer, default=0)
    extractos_nuevos = Column(Integer, default=0)
    # Última corrida COMPLETA (es la que ve el tablero de conexiones).
    ultima_sync = Column(DateTime, nullable=True)
    ultimo_leidos = Column(Integer, default=0)
    ultimo_nuevos = Column(Integer, default=0)
    ultimo_extractos = Column(Integer, default=0)
    ultimo_error = Column(String, nullable=True)
    ultimo_error_en = Column(DateTime, nullable=True)


class ClavePdf(Base):
    """Clave con la que se abren los extractos cifrados (normalmente la
    cédula). Se guarda cifrada con Fernet, igual que el refresh token."""
    __tablename__ = "claves_pdf"

    usuario_id = Column(String, primary_key=True)
    clave_enc = Column(String, nullable=False)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False, unique=True)
    p256dh = Column(String, nullable=False)
    auth = Column(String, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)


class HistorialExtracto(Base):
    __tablename__ = "historial_extractos"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    cuenta_id = Column(String, nullable=False)
    banco_detectado = Column(String, default="desconocido")
    total_movimientos = Column(Integer, default=0)
    exactos = Column(Integer, default=0)
    aproximados = Column(Integer, default=0)
    faltantes = Column(Integer, default=0)
    descartados = Column(Integer, default=0)
    importados = Column(Integer, default=0)
    estado = Column(String, default="pendiente_revision")  # pendiente_revision | conciliado | error
    review_json = Column(String, default="[]")  # snapshot del review para reabrir sin re-subir el PDF
    creado_en = Column(DateTime, default=datetime.utcnow)


class Consentimiento(Base):
    """Registro AUDITABLE de autorizaciones de tratamiento de datos (Ley 1581 de 2012).
    Solo se INSERTA: nunca se actualiza ni se borra. Revocar = nueva fila con
    aceptado=False; el estado vigente de una finalidad es su fila más reciente."""
    __tablename__ = "consentimientos"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False)  # versión de los textos legales aceptada (ej. "1.1")
    finalidad = Column(String, nullable=False)  # tratamiento_basico | lectura_correo | ia | notificaciones
    aceptado = Column(Boolean, nullable=False)
    creado_en_utc = Column(DateTime, nullable=False, default=datetime.utcnow)
    creado_en_co = Column(DateTime, nullable=False)  # la misma fecha en hora Colombia (UTC-5)
    ip = Column(String, nullable=True)  # opcional; puede no estar disponible
    origen = Column(String, default="app")  # app | registro | perfil | flujo_gmail | flujo_ia


class Categoria(Base):
    """Categorías de movimientos por usuario. Las 8 base (Comida, Transporte,
    etc.) se crean automáticamente la primera vez que el usuario pide su
    lista y no tiene ninguna — así puede renombrarlas, ocultarlas o agregar
    las suyas propias (ej. "Mascotas") sin que queden fijas en el código."""
    __tablename__ = "categorias"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    icono = Column(String, default="🏷️")
    orden = Column(Integer, default=0)
    activa = Column(Boolean, default=True)  # oculta en vez de borrar, para no perder el historial de movimientos ya categorizados con ella
    es_base = Column(Boolean, default=False)  # una de las 8 originales — no se puede eliminar, solo ocultar o renombrar
    color = Column(String, nullable=True)  # opcional, "#RRGGBB"
    tipo = Column(String, default="ambos")  # gasto | ingreso | ambos
    creado_en = Column(DateTime, default=datetime.utcnow)
