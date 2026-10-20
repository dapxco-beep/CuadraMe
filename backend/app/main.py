import os
from datetime import datetime, timezone

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine
from app.rls import asegurar_rls
from app.compresion import GZipSelectivo
from app.seguridad import SeguridadMiddleware, limpiar_evento_sentry
from app import migraciones
from app import models_asistente  # noqa: F401  (registra la tabla uso_asistente para create_all)
from app import limites_diarios  # noqa: F401  (registra la tabla uso_diario para create_all)
from app import models_pendientes  # noqa: F401  (registra comercios_silenciados para create_all)
from app import models_comentarios  # noqa: F401  (registra la tabla comentarios para create_all)
from app import models_rendimientos  # noqa: F401  (registra cajitas y tasas_referencia para create_all)
from app import models_avisos  # noqa: F401  (registra eventos_actividad y ajustes_avisos para create_all)
from app import models_autoarreglo  # noqa: F401  (registra arreglos_auto para create_all)
from app import avisos as avisos_servicio  # noqa: F401  (registra la tabla eventos_actividad y los ganchos de activación)
from app.routers import (
    ahorcado,
    asistente,
    avisos,
    salud,
    backup,
    categorias,
    subcategorias,
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
    traslados,
    impuestos,
    insights,
    metas,
    metricas,
    movimientos,
    por_categorizar,
    pagos,
    patrimonio,
    inversiones,
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

if engine.dialect.name == "postgresql":
    # Columnas/índices nuevos en tablas ya existentes: app/migraciones.py (versionadas, una vez
    # cada una, idempotentes). create_all solo crea tablas nuevas. Ver docs/MIGRACIONES.md.
    migraciones.aplicar(engine)
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
# El más interno de todos: un error inesperado se convierte en un 500 normal que SÍ pasa por CORS. Sin esto
# Starlette lo responde desde su capa externa, sin cabeceras CORS, y el navegador lo muestra como «sin
# conexión» aunque el servidor esté arriba (así pasó cuando faltó una columna tras un despliegue).
from app.errores_500 import Errores500Middleware  # noqa: E402

app.add_middleware(Errores500Middleware)
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
app.include_router(por_categorizar.router)
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
app.include_router(subcategorias.router)
app.include_router(backup.router)
app.include_router(metricas.router)
app.include_router(patrimonio.router)
app.include_router(inversiones.router)
app.include_router(planificacion.router)
app.include_router(gastos_compartidos.router)
app.include_router(facturas.router)
app.include_router(asistente.router)
app.include_router(importar.router)
app.include_router(impuestos.router)
app.include_router(cierre.router)
app.include_router(consentimientos.router)
app.include_router(informes.router)
app.include_router(traslados.router)
app.include_router(conexiones.router)
app.include_router(cuotas_tarjeta.router)
app.include_router(extracto_tarjeta.router)
app.include_router(resumen.router)
app.include_router(recordatorios.router)
app.include_router(consejos.router)
app.include_router(comentarios.router)
app.include_router(avisos.router)
app.include_router(salud.router)
app.include_router(rendimientos.router)
from app.routers import sincronizacion  # noqa: E402

app.include_router(sincronizacion.router)
from app.routers import costos_bancarios as costos_bancarios_router  # noqa: E402

app.include_router(costos_bancarios_router.router)
from app.routers import cuadre as cuadre_router  # noqa: E402

app.include_router(cuadre_router.router)
from app.routers import reglas_correo as reglas_correo_router  # noqa: E402

app.include_router(reglas_correo_router.router)
from app.routers import formas_asunto as formas_asunto_router  # noqa: E402

app.include_router(formas_asunto_router.router)
from app.routers import autoarreglo as autoarreglo_router  # noqa: E402

app.include_router(autoarreglo_router.router)


@app.get("/health")
def health():
    return {"ok": True}


VERSION_SERVIDOR = "1.0.0"
_ARRANQUE_EN = datetime.now(timezone.utc).isoformat(timespec="seconds")


@app.get("/version")
def version():
    """Pública y sin datos sensibles: sirve para saber qué compilación del servidor responde.
    (/health no cambia: los monitores esperan {"ok": true}.)"""
    commit = (
        os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("GIT_COMMIT_SHA")
        or os.environ.get("SOURCE_COMMIT")
        or ""
    )
    return {
        "servicio": "cuadrame-backend",
        "version": VERSION_SERVIDOR,
        "commit": commit[:7] or "dev",
        "arranque_en": _ARRANQUE_EN,
    }
