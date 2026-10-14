import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine
from app.rls import asegurar_rls
from app.compresion import GZipSelectivo
from app.seguridad import SeguridadMiddleware, limpiar_evento_sentry
from app import models_asistente  # noqa: F401  (registra la tabla uso_asistente para create_all)
from app import limites_diarios  # noqa: F401  (registra la tabla uso_diario para create_all)
from app import models_comentarios  # noqa: F401  (registra la tabla comentarios para create_all)
from app import models_rendimientos  # noqa: F401  (registra cajitas y tasas_referencia para create_all)
from app import models_avisos  # noqa: F401  (registra eventos_actividad y ajustes_avisos para create_all)
from app import avisos as avisos_servicio  # noqa: F401  (registra la tabla eventos_actividad y los ganchos de activación)
from app.routers import (
    ahorcado,
    asistente,
    avisos,
    backup,
    categorias,
    cierre,
    comentarios,
    compartir,
    conciliacion,
    conexiones,
    consejos,
    consentimientos,
    correos,
    cuentas,
    cuotas_tarjeta,
    deudas,
    duplicados,
    exportar,
    extracto_tarjeta,
    facturas,
    gastos_compartidos,
    importar,
    informes,
    impuestos,
    insights,
    metas,
    metricas,
    movimientos,
    pagos,
    patrimonio,
    planificacion,
    perfil,
    presupuestos,
    push,
    recordatorios,
    recurrentes,
    rendimientos,
    reglas,
    reportes,
    resumen,
)

Base.metadata.create_all(bind=engine)

# No hay sistema de migraciones (Alembic) en este proyecto: create_all crea
# tablas nuevas pero no altera columnas en tablas ya existentes en producción.
# Este bloque agrega, de forma idempotente, columnas nuevas que el modelo
# necesita y que la tabla en producción aún no tiene.
if engine.dialect.name == "postgresql":
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE recurrentes ADD COLUMN IF NOT EXISTS "
            "ultima_notificacion_vencimiento TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS "
            "descartados INTEGER DEFAULT 0"
        ))
        conn.execute(text(
            "ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS "
            "confianza_autoimport FLOAT DEFAULT 0.75"
        ))
        conn.execute(text(
            "ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS "
            "autoimportar_extractos BOOLEAN DEFAULT FALSE"
        ))
        conn.execute(text(
            "ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS "
            "sobre_ajuste FLOAT DEFAULT 0"
        ))
        conn.execute(text(
            "ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS "
            "ultima_alerta_mes VARCHAR"
        ))
        # Metas con sugerencia: fecha del último aporte a mano (supabase/migraciones/metas_sugerencia_bancos.sql).
        # Correo en dos usos independientes (movimientos / extractos); por defecto activos.
        conn.execute(text("ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS gmail_leer_movimientos BOOLEAN DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS gmail_leer_extractos BOOLEAN DEFAULT TRUE"))
        # Fecha del movimiento leida del texto del correo (supabase/migraciones/correos_fecha_movimiento.sql).
        conn.execute(text("ALTER TABLE correos_gastos ADD COLUMN IF NOT EXISTS fecha_movimiento TIMESTAMP"))
        for _col, _tipo in (
            ("tipo", "VARCHAR DEFAULT 'todo'"), ("leidos_mov", "INTEGER DEFAULT 0"),
            ("leidos_ext", "INTEGER DEFAULT 0"), ("omitidos_mov", "INTEGER DEFAULT 0"),
            ("ultima_sync_mov", "TIMESTAMP"), ("ultima_sync_ext", "TIMESTAMP"),
            ("ultimo_leidos_mov", "INTEGER DEFAULT 0"), ("ultimo_leidos_ext", "INTEGER DEFAULT 0"),
            ("ultimo_ya_registrados", "INTEGER DEFAULT 0"),
        ):
            conn.execute(text(f"ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS {_col} {_tipo}"))
        conn.execute(text("ALTER TABLE metas ADD COLUMN IF NOT EXISTS ultimo_aporte TIMESTAMP NULL"))
        # Buzón «Mi banco no está»: nombre del banco y archivo de muestra en almacenamiento privado
        # (mismo archivo .sql). Opcionales.
        conn.execute(text("ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS banco VARCHAR NULL"))
        conn.execute(text("ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS adjunto_ruta VARCHAR NULL"))
        conn.execute(text("ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS adjunto_nombre VARCHAR NULL"))
        conn.execute(text("ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS adjunto_bytes INTEGER NULL"))
        # Tarjetas de crédito reales: cupo, corte, pago y tasa en la cuenta.
        # (La misma lista, como SQL suelto, está en supabase/migraciones/.)
        conn.execute(text("ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS cupo_total FLOAT"))
        conn.execute(text("ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS dia_corte INTEGER"))
        conn.execute(text("ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS dia_pago INTEGER"))
        conn.execute(text("ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS tasa_ea FLOAT"))
        conn.execute(text("ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS ultima_alerta_pago VARCHAR"))
        # Categorías libres y categorización automática transparente.
        # DEFAULT TRUE deja los movimientos existentes como "confirmados".
        # (Como SQL suelto: supabase/migraciones/categorias_auto.sql.)
        conn.execute(text("ALTER TABLE categorias ADD COLUMN IF NOT EXISTS color VARCHAR"))
        conn.execute(text("ALTER TABLE categorias ADD COLUMN IF NOT EXISTS es_sistema BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE categorias ADD COLUMN IF NOT EXISTS tipo VARCHAR DEFAULT 'ambos'"))
        conn.execute(text("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS cat_origen VARCHAR"))
        conn.execute(text("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS cat_confirmada BOOLEAN DEFAULT TRUE"))
        # Registro con Apple Wallet: alias de tarjeta y recordatorio nocturno.
        # (Como SQL suelto: supabase/migraciones/wallet_recordatorio.sql.)
        conn.execute(text("ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS alias_tarjeta VARCHAR"))
        conn.execute(text("ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS recordatorio_diario BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS ultimo_recordatorio VARCHAR"))
        # Resumen semanal por correo (supabase/migraciones/resumen_semanal.sql).
        conn.execute(text("ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS resumen_correo BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS email_resumen VARCHAR"))
        # Push semanal sin montos si la persona oculta saldos (supabase/migraciones/respaldo_y_push_semanal.sql).
        conn.execute(text("ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS ocultar_montos BOOLEAN DEFAULT FALSE"))
        # Cruce con el extracto (supabase/migraciones/cierre_app_conciliacion.sql).
        conn.execute(text("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS conciliado_en TIMESTAMP NULL"))
        conn.execute(text("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS extracto_id VARCHAR NULL"))
        # Tablero "Conexiones": último uso de la API key (Atajo de iPhone).
        # (Como SQL suelto: supabase/migraciones/sync_gmail_conexiones.sql.)
        conn.execute(text("ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS api_key_ultimo_uso TIMESTAMP"))
        # Monitor de crecimiento: fecha de alta del perfil (supabase/migraciones/perfil_creado_en.sql).
        conn.execute(text("ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS creado_en TIMESTAMP"))
        # Deduplicación entre canales (supabase/migraciones/duplicados_canales.sql). Opcionales.
        conn.execute(text("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS origen VARCHAR NULL"))
        conn.execute(text("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS huella_externa VARCHAR NULL"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_movimientos_huella "
            "ON movimientos (usuario_id, huella_externa)"
        ))
        # Punto de partida (supabase/migraciones/punto_de_partida.sql). Opcionales.
        conn.execute(text("ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_modo VARCHAR NULL"))
        conn.execute(text("ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_fecha DATE NULL"))
        conn.execute(text("ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_saldos VARCHAR NULL"))
        conn.execute(text("ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_en TIMESTAMP NULL"))
        # Resultado de probar la clave del PDF en cada extracto (mismo archivo .sql).
        conn.execute(text("ALTER TABLE extractos_correo ADD COLUMN IF NOT EXISTS clave_resultado VARCHAR NULL"))
        conn.execute(text("ALTER TABLE extractos_correo ADD COLUMN IF NOT EXISTS clave_probada_en TIMESTAMP NULL"))
        # Cuadre con el extracto (supabase/migraciones/cuadre_extracto.sql). Todo opcional.
        for _col, _tipo in (
            ("saldo_inicial_extracto", "FLOAT"), ("saldo_final_extracto", "FLOAT"), ("fecha_corte", "VARCHAR"),
            ("periodo_inicio", "VARCHAR"), ("moneda", "VARCHAR"), ("saldos_origen", "VARCHAR"),
            ("cuadre_estado", "VARCHAR"), ("cuadre_diferencia", "FLOAT"), ("cuadre_en", "TIMESTAMP"),
        ):
            conn.execute(text(f"ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS {_col} {_tipo} NULL"))
        # Casi toda consulta filtra por cuenta y ordena/filtra por fecha.
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_movimientos_cuenta_fecha "
            "ON movimientos (cuenta_id, fecha DESC)"
        ))
    # Las tablas recién creadas por create_all nacen sin RLS: se activa aquí
    # (tolerante a fallos; ver app/rls.py).
    asegurar_rls(engine)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        # 10% de las requests normales se muestrean para performance, pero
        # el 100% de los errores se reporta siempre — no queremos perdernos
        # ninguno por muestreo en una beta con pocos usuarios.
        traces_sample_rate=0.1,
        send_default_pii=False,  # no mandar datos personales del usuario a Sentry
        include_local_variables=False,  # las variables locales traen tokens, claves de PDF y montos
        before_send=limpiar_evento_sentry,
    )

# En producción no se exponen /docs, /redoc ni /openapi.json: son un mapa
# completo de la API para quien quiera atacarla. En local siguen disponibles.
_es_prod = settings.environment == "production"
app = FastAPI(
    title="CuadraMe API",
    docs_url=None if _es_prod else "/docs",
    redoc_url=None if _es_prod else "/redoc",
    openapi_url=None if _es_prod else "/openapi.json",
)

# Los Atajos de iPhone leen "mensaje" de la respuesta: en /movimientos/rapido* los errores lo traen.
from app import errores_atajo  # noqa: E402

errores_atajo.registrar(app)

# Va ANTES que CORS a propósito: add_middleware apila de afuera hacia adentro, así que
# CORS queda como capa externa y hasta un 413 sale con sus cabeceras CORS (si no, el
# navegador lo mostraría como "error de red" en vez del mensaje claro).
app.add_middleware(SeguridadMiddleware, con_csp=_es_prod)

# Compresión gzip de lo que pasa de 1 KB (JSON de listas y reportes): ver app/compresion.py.
# Va después de SeguridadMiddleware y antes de CORS: CORS sigue siendo la capa externa.
app.add_middleware(GZipSelectivo)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        settings.pwa_url,
        *[o.strip() for o in settings.cors_origins_extra.split(",") if o.strip()],
    ],
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # El navegador recuerda el permiso (preflight) en vez de repetirlo antes de cada lectura:
    # cada preflight es un viaje de ida y vuelta extra. Chrome limita este valor a 2 h.
    max_age=7200,
)

app.include_router(cuentas.router)
app.include_router(movimientos.router)
app.include_router(pagos.router)
app.include_router(presupuestos.router)
app.include_router(reportes.router)
app.include_router(metas.router)
app.include_router(recurrentes.router)
app.include_router(deudas.router)
app.include_router(conciliacion.router)
app.include_router(duplicados.router)
app.include_router(perfil.router)
app.include_router(correos.router)
app.include_router(insights.router)
app.include_router(push.router)
app.include_router(exportar.router)
app.include_router(compartir.router)
app.include_router(reglas.router)
app.include_router(ahorcado.router)
app.include_router(categorias.router)
app.include_router(backup.router)
app.include_router(metricas.router)
app.include_router(patrimonio.router)
app.include_router(planificacion.router)
app.include_router(gastos_compartidos.router)
app.include_router(facturas.router)
app.include_router(asistente.router)
app.include_router(importar.router)
app.include_router(impuestos.router)
app.include_router(cierre.router)
app.include_router(consentimientos.router)
app.include_router(informes.router)
app.include_router(conexiones.router)
app.include_router(cuotas_tarjeta.router)
app.include_router(extracto_tarjeta.router)
app.include_router(resumen.router)
app.include_router(recordatorios.router)
app.include_router(consejos.router)
app.include_router(comentarios.router)
app.include_router(avisos.router)
app.include_router(rendimientos.router)
from app.routers import sincronizacion  # noqa: E402

app.include_router(sincronizacion.router)
from app.routers import costos_bancarios as costos_bancarios_router  # noqa: E402

app.include_router(costos_bancarios_router.router)
from app.routers import cuadre as cuadre_router  # noqa: E402

app.include_router(cuadre_router.router)


@app.get("/health")
def health():
    return {"ok": True}
