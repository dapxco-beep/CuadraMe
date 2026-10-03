import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine
from app import models_asistente  # noqa: F401  (registra la tabla uso_asistente para create_all)
from app.routers import (
    ahorcado,
    asistente,
    backup,
    categorias,
    cierre,
    compartir,
    conciliacion,
    correos,
    cuentas,
    deudas,
    exportar,
    facturas,
    gastos_compartidos,
    importar,
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
    recurrentes,
    reglas,
    reportes,
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
        # Casi toda consulta filtra por cuenta y ordena/filtra por fecha.
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_movimientos_cuenta_fecha "
            "ON movimientos (cuenta_id, fecha DESC)"
        ))

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        # 10% de las requests normales se muestrean para performance, pero
        # el 100% de los errores se reporta siempre — no queremos perdernos
        # ninguno por muestreo en una beta con pocos usuarios.
        traces_sample_rate=0.1,
        send_default_pii=False,  # no mandar datos personales del usuario a Sentry
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


@app.get("/health")
def health():
    return {"ok": True}
