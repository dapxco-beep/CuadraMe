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
    # Dos usos independientes del correo (ambos activos por defecto = comportamiento de siempre):
    # movimientos = notificaciones del banco (día a día); extractos = PDF del estado de cuenta (conciliar).
    gmail_leer_movimientos = Column(Boolean, default=True)
    gmail_leer_extractos = Column(Boolean, default=True)
    confianza_autoimport = Column(Float, default=0.75)  # 0.5-0.95: qué tan segura debe estar la categorización antes de auto-importar un movimiento sin preguntar
    # Importar solos, al subir un extracto, los movimientos que la app categoriza con certeza
    # (umbral = confianza_autoimport). Apagado por defecto: nada se importa sin que el usuario confirme.
    autoimportar_extractos = Column(Boolean, default=False)
    # Recordatorio nocturno (8pm Colombia) si hoy no registró nada; opcional.
    recordatorio_diario = Column(Boolean, default=False)
    ultimo_recordatorio = Column(String, nullable=True)  # YYYY-MM-DD del último aviso, para no repetir
    # Última vez que alguien usó la API key (Atajo de iPhone, Tasker...): alimenta el semáforo de "Conexiones".
    api_key_ultimo_uso = Column(DateTime, nullable=True)
    # Cómo le decimos a la persona (saludos, resumen semanal, push). Opcionales: sin nombre todo se lee igual.
    nombre_preferido = Column(String, nullable=True)
    nombre_confirmado = Column(Boolean, default=False)  # ya respondió (o dijo «Ahora no»): no se vuelve a preguntar
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Cuándo se creó el perfil (= primer uso): alimenta la tendencia de usuarios de «Salud del negocio».
    # Los perfiles anteriores quedan en NULL y se estiman con su primer movimiento.
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=True)
    # País del usuario (ISO: CO, MX, CL, PE...). `deferred`: la app arranca aunque las columnas aún
    # no existan en la base (supabase/migraciones/perfil_pais.sql). NULL = perfil anterior -> CO.
    pais = deferred(Column(String, nullable=True))
    moneda_base = deferred(Column(String, nullable=True))  # moneda en que se muestran informes y patrimonio
    # Nombre completo del titular (de Google): SOLO para reconocer traslados propios en los extractos
    # («Enviaste a DANIEL ALFONSO PARRADO»). No se muestra ni se envía fuera. supabase/migraciones/perfil_nombre_titular.sql
    nombre_titular = deferred(Column(String, nullable=True))
    zona_horaria = deferred(Column(String, nullable=True))
    idioma = deferred(Column(String, nullable=True))  # es-CO, es-MX, es-AR...
    pais_confirmado = deferred(Column(Boolean, nullable=True))  # la persona lo eligió/confirmó (no solo sugerido)


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
    # Opcional: detalle dentro de la categoría (ver docs/SUBCATEGORIAS.md). NULL = solo categoría.
    subcategoria = Column(String, nullable=True)
    tipo = Column(String, nullable=True)  # income | expense | transfer | null (no forzar tipo)
    prioridad = Column(Integer, default=0)  # reglas con mayor prioridad se evalúan primero
    creado_en = Column(DateTime, default=datetime.utcnow)
    # En pausa (False) = no se aplica a movimientos nuevos, pero no se pierde. NULL = activa.
    activa = Column(Boolean, default=True)


class ReglaTitulo(Base):
    """«Recordar este nombre para este comercio»: huella del comercio -> título elegido por la persona.
    Solo existe si la persona lo pidió; se aplica a movimientos nuevos (ver app/titulo.py)."""
    __tablename__ = "reglas_titulo"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    huella = Column(String, nullable=False)
    titulo = Column(String, nullable=False)
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
    # Opcional: detalle dentro de la categoría («Transporte · Gasolina»). La categoría sigue siendo la
    # que agrega en informes/presupuestos; esto solo desglosa. NULL = sin subcategoría.
    subcategoria = Column(String, nullable=True)
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
    # Nombre que le puso la PERSONA («Recibo de la luz»). `descripcion` sigue siendo el texto original del
    # banco: el anti-duplicados, la conciliación y las reglas por comercio trabajan con él. NULL = sin título.
    titulo = Column(String, nullable=True)


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
    ultimo_aporte = Column(DateTime, nullable=True)  # último aporte hecho a mano (alimenta «meta sin aporte este mes»)
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
    # Fecha (y hora) del MOVIMIENTO que el banco escribio en el texto del correo, en UTC como `recibido_en`.
    # NULL = no la trae (vale la de recepcion) o es un correo viejo (se calcula al vuelo al listar).
    fecha_movimiento = Column(DateTime, nullable=True)
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
    # Resultado del último intento de abrirlo con la clave guardada: 'ok' | 'fallo' | NULL (nunca
    # probado). Nunca guarda la clave. `clave_probada_en` permite saber si la clave se cambió después.
    clave_resultado = Column(String, nullable=True)
    clave_probada_en = Column(DateTime, nullable=True)
    # Por qué no se pudo leer (ver app/extractos_vista.MOTIVOS): opcional; NULL = sin error o error antiguo.
    motivo_error = Column(String, nullable=True)
    # JSON con SOLO 4 datos que el cuerpo del aviso de la tarjeta trae (pago mínimo, período facturado, fecha de
    # corte, fecha límite). El cuerpo del correo nunca se guarda. Útil aunque el PDF no se pueda abrir.
    datos_cuerpo = Column(String, nullable=True)


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
    # Carriles: qué lee la corrida (todo | movimientos | extractos) y su estado por separado.
    tipo = Column(String, default="todo")
    leidos_mov = Column(Integer, default=0)
    leidos_ext = Column(Integer, default=0)
    omitidos_mov = Column(Integer, default=0)
    ultima_sync_mov = Column(DateTime, nullable=True)
    ultima_sync_ext = Column(DateTime, nullable=True)
    ultimo_leidos_mov = Column(Integer, default=0)
    ultimo_leidos_ext = Column(Integer, default=0)
    ultimo_ya_registrados = Column(Integer, default=0)
    # Resumen de la última lectura de MOVIMIENTOS (solo cifras y fechas; nunca contenido de correos).
    resumen_mov_curso = Column(String, nullable=True)  # JSON con lo descartado mientras corre la lectura
    ultimo_resumen_mov = Column(String, nullable=True)  # JSON del resumen de la última lectura completa
    ceros_seguidos_mov = Column(Integer, default=0)  # lecturas completas seguidas de movimientos con 0 correos


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
    # Cuadre con el extracto (app/cuadre_extracto.py). Todos opcionales: un extracto sin saldos
    # legibles funciona como siempre. Los saldos van en la convención de la cuenta: en una tarjeta
    # de crédito la deuda es NEGATIVA (-800.000 = debes 800.000).
    saldo_inicial_extracto = Column(Float, nullable=True)
    saldo_final_extracto = Column(Float, nullable=True)
    fecha_corte = Column(String, nullable=True)  # AAAA-MM-DD: fecha a la que el banco da el saldo final
    periodo_inicio = Column(String, nullable=True)  # AAAA-MM-DD: primer día del extracto
    moneda = Column(String, nullable=True)  # COP | USD ... si el extracto la dice
    saldos_origen = Column(String, nullable=True)  # extracto | tabla | manual
    cuadre_estado = Column(String, nullable=True)  # cuadra | diferencia (última vez que se midió)
    cuadre_diferencia = Column(Float, nullable=True)
    cuadre_en = Column(DateTime, nullable=True)
    # Solo si estado = 'error': por qué no se pudo leer (ver app/extractos_vista.MOTIVOS). Opcional.
    motivo_error = Column(String, nullable=True)
    # Extracto de la TARJETA de Nu: resumen de la página 1 + comprobaciones de la lectura (JSON, ver extractos_tarjeta_nu).
    lectura_json = Column(String, nullable=True)

    @property
    def lectura(self) -> dict | None:
        import json
        try:
            d = json.loads(self.lectura_json) if self.lectura_json else None
        except ValueError:
            return None
        return d if isinstance(d, dict) else None

    @property
    def lectura_completa(self) -> bool | None:
        d = self.lectura
        return d.get("lectura_completa") if d else None

    @property
    def mensaje_lectura(self) -> str | None:
        d = self.lectura
        return d.get("mensaje_lectura") if d else None


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
    es_sistema = Column(Boolean, default=False)  # la crea la app (intereses, 4x1000, rendimientos...): no sale en presupuestos por defecto, sí en informes
    creado_en = Column(DateTime, default=datetime.utcnow)


class Subcategoria(Base):
    """Detalle opcional DENTRO de una categoría (Transporte > Gasolina, Uber). Un solo nivel.
    Se referencia por NOMBRE de la categoría padre (igual que movimientos, reglas y presupuestos
    referencian la categoría). Nombre único por (usuario, padre). Ver docs/SUBCATEGORIAS.md."""
    __tablename__ = "subcategorias"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    categoria_padre = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    orden = Column(Integer, default=0)
    creado_en = Column(DateTime, default=datetime.utcnow)


class TasaManual(Base):
    """Tasa que la persona puso a mano cuando no hay tasa automática: 1 `moneda` = `tasa` de su moneda
    `base`. Privada por usuario (fase 2 de moneda base)."""
    __tablename__ = "tasas_manuales"
    __table_args__ = (UniqueConstraint("usuario_id", "moneda", "base", name="uq_tasa_manual"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    moneda = Column(String, nullable=False)
    base = Column(String, nullable=False)
    tasa = Column(Float, nullable=False)
    fecha = Column(String, nullable=True)
