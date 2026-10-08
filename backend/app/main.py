import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine
from app.rls import asegurar_rls
from app.seguridad import SeguridadMiddleware, limpiar_evento_sentry
from app import models_asistente  # noqa: F401  (registra la tabla uso_asistente para create_all)
from app import limites_diarios  # noqa: F401  (registra la tabla uso_diario para create_all)
from app.routers import (
    ahorcado,
    asistente,
    backup,
    categorias,
    cierre,
    compartir,
    conciliacion,
    conexiones,
    consejos,
    consentimientos,
    correos,
    cuentas,
    cuotas_tarjeta,
    deudas,
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
        # Cruce con el extracto (supabase/migraciones/cierre_app_conciliacion.sql).
        conn.execute(text("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS conciliado_en TIMESTAMP NULL"))
        conn.execute(text("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS extracto_id VARCHAR NULL"))
        # Tablero "Conexiones": último uso de la API key (Atajo de iPhone).
        # (Como SQL suelto: supabase/migraciones/sync_gmail_conexiones.sql.)
        conn.execute(text("ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS api_key_ultimo_uso TIMESTAMP"))
        # Monitor de crecimiento: fecha de alta del perfil (supabase/migraciones/perfil_creado_en.sql).
        conn.execute(text("ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS creado_en TIMESTAMP"))
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
from app.routers import sincronizacion  # noqa: E402

app.include_router(sincronizacion.router)


@app.get("/health")
def health():
    return {"ok": True}
