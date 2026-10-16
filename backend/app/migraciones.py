"""Migraciones versionadas del esquema (ver docs/MIGRACIONES.md).

Cada migración tiene un id único y ordenado, y una lista de sentencias SQL IDEMPOTENTES
(ADD COLUMN IF NOT EXISTS, CREATE INDEX IF NOT EXISTS). Se aplican al arrancar, una sola
vez cada una, y quedan registradas en la tabla schema_migrations.
"""
import logging

from sqlalchemy import text

log = logging.getLogger(__name__)

# Para que dos instancias que arrancan a la vez no apliquen lo mismo en paralelo.
_LOCK_ID = 7_340_001

# Lista ORDENADA. NUNCA edites ni reordenes una migración ya desplegada: agrega una al final.
MIGRACIONES: list[tuple[str, list[str]]] = [
    (
        "0001_columnas_historicas",
        [
            'ALTER TABLE recurrentes ADD COLUMN IF NOT EXISTS ultima_notificacion_vencimiento TIMESTAMP',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS descartados INTEGER DEFAULT 0',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS confianza_autoimport FLOAT DEFAULT 0.75',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS autoimportar_extractos BOOLEAN DEFAULT FALSE',
            'ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS sobre_ajuste FLOAT DEFAULT 0',
            'ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS ultima_alerta_mes VARCHAR',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS motivo_error VARCHAR NULL',
            'ALTER TABLE extractos_correo ADD COLUMN IF NOT EXISTS motivo_error VARCHAR NULL',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS gmail_leer_movimientos BOOLEAN DEFAULT TRUE',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS gmail_leer_extractos BOOLEAN DEFAULT TRUE',
            'ALTER TABLE correos_gastos ADD COLUMN IF NOT EXISTS fecha_movimiento TIMESTAMP',
            "ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS tipo VARCHAR DEFAULT 'todo'",
            'ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS leidos_mov INTEGER DEFAULT 0',
            'ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS leidos_ext INTEGER DEFAULT 0',
            'ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS omitidos_mov INTEGER DEFAULT 0',
            'ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS ultima_sync_mov TIMESTAMP',
            'ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS ultima_sync_ext TIMESTAMP',
            'ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS ultimo_leidos_mov INTEGER DEFAULT 0',
            'ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS ultimo_leidos_ext INTEGER DEFAULT 0',
            'ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS ultimo_ya_registrados INTEGER DEFAULT 0',
            'ALTER TABLE metas ADD COLUMN IF NOT EXISTS ultimo_aporte TIMESTAMP NULL',
            'ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS banco VARCHAR NULL',
            'ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS adjunto_ruta VARCHAR NULL',
            'ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS adjunto_nombre VARCHAR NULL',
            'ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS adjunto_bytes INTEGER NULL',
            'ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS cupo_total FLOAT',
            'ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS dia_corte INTEGER',
            'ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS dia_pago INTEGER',
            'ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS tasa_ea FLOAT',
            'ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS ultima_alerta_pago VARCHAR',
            'ALTER TABLE categorias ADD COLUMN IF NOT EXISTS color VARCHAR',
            'ALTER TABLE categorias ADD COLUMN IF NOT EXISTS es_sistema BOOLEAN DEFAULT FALSE',
            "ALTER TABLE categorias ADD COLUMN IF NOT EXISTS tipo VARCHAR DEFAULT 'ambos'",
            'ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS cat_origen VARCHAR',
            'ALTER TABLE reglas_categoria ADD COLUMN IF NOT EXISTS activa BOOLEAN DEFAULT TRUE',
            'ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS cat_confirmada BOOLEAN DEFAULT TRUE',
            'ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS alias_tarjeta VARCHAR',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS recordatorio_diario BOOLEAN DEFAULT FALSE',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS ultimo_recordatorio VARCHAR',
            'ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS resumen_correo BOOLEAN DEFAULT FALSE',
            'ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS email_resumen VARCHAR',
            'ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS ocultar_montos BOOLEAN DEFAULT FALSE',
            'ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS conciliado_en TIMESTAMP NULL',
            'ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS extracto_id VARCHAR NULL',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS api_key_ultimo_uso TIMESTAMP',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS creado_en TIMESTAMP',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS nombre_preferido VARCHAR NULL',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS nombre_confirmado BOOLEAN DEFAULT FALSE',
            'ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS origen VARCHAR NULL',
            'ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS huella_externa VARCHAR NULL',
            'CREATE INDEX IF NOT EXISTS ix_movimientos_huella ON movimientos (usuario_id, huella_externa)',
            'ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_modo VARCHAR NULL',
            'ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_fecha DATE NULL',
            'ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_saldos VARCHAR NULL',
            'ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_en TIMESTAMP NULL',
            'ALTER TABLE extractos_correo ADD COLUMN IF NOT EXISTS clave_resultado VARCHAR NULL',
            'ALTER TABLE extractos_correo ADD COLUMN IF NOT EXISTS clave_probada_en TIMESTAMP NULL',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS saldo_inicial_extracto FLOAT NULL',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS saldo_final_extracto FLOAT NULL',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS fecha_corte VARCHAR NULL',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS periodo_inicio VARCHAR NULL',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS moneda VARCHAR NULL',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS saldos_origen VARCHAR NULL',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS cuadre_estado VARCHAR NULL',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS cuadre_diferencia FLOAT NULL',
            'ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS cuadre_en TIMESTAMP NULL',
            'ALTER TABLE activos_patrimonio ADD COLUMN IF NOT EXISTS arriendo_mensual FLOAT NULL',
            'ALTER TABLE activos_patrimonio ADD COLUMN IF NOT EXISTS anio FLOAT NULL',
            'ALTER TABLE activos_patrimonio ADD COLUMN IF NOT EXISTS depreciacion_pct FLOAT NULL',
            'ALTER TABLE activos_patrimonio ADD COLUMN IF NOT EXISTS deuda_id VARCHAR NULL',
            'ALTER TABLE activos_patrimonio ADD COLUMN IF NOT EXISTS broker VARCHAR NULL',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS pais VARCHAR NULL',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS moneda_base VARCHAR NULL',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS zona_horaria VARCHAR NULL',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS idioma VARCHAR NULL',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS pais_confirmado BOOLEAN NULL',
            'CREATE INDEX IF NOT EXISTS ix_movimientos_cuenta_fecha ON movimientos (cuenta_id, fecha DESC)',
        ],
    ),
    (
        # Columnas que se agregaron DESPUÉS de desplegar 0001 (por eso van aparte: una migración ya
        # aplicada no se vuelve a ejecutar, y producción dio 500 por faltar datos_cuerpo).
        "0002_nombre_titular_y_datos_cuerpo",
        [
            'ALTER TABLE extractos_correo ADD COLUMN IF NOT EXISTS datos_cuerpo VARCHAR NULL',
            'ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS nombre_titular VARCHAR NULL',
        ],
    ),
    (
        # Subcategorías (un nivel dentro de cada categoría). Todo opcional: lo existente no cambia.
        "0003_subcategorias",
        [
            'CREATE TABLE IF NOT EXISTS subcategorias ('
            'id VARCHAR PRIMARY KEY, usuario_id VARCHAR NOT NULL, categoria_padre VARCHAR NOT NULL, '
            'nombre VARCHAR NOT NULL, orden INTEGER DEFAULT 0, creado_en TIMESTAMP)',
            'CREATE INDEX IF NOT EXISTS ix_subcategorias_usuario ON subcategorias (usuario_id)',
            'ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS subcategoria VARCHAR NULL',
            'ALTER TABLE reglas_categoria ADD COLUMN IF NOT EXISTS subcategoria VARCHAR NULL',
        ],
    ),
]


def aplicar(engine, migraciones=None) -> list[str]:
    """Aplica las migraciones pendientes y devuelve los ids aplicados en esta llamada.

    Cada migración corre en su propia transacción junto con su registro en schema_migrations:
    o se aplica completa y queda anotada, o no deja nada. En PostgreSQL un advisory lock
    serializa las instancias concurrentes; quien llega segundo ve la migración ya anotada.
    """
    migraciones = MIGRACIONES if migraciones is None else migraciones
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "id VARCHAR PRIMARY KEY, aplicada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        ))
    aplicadas: list[str] = []
    for mid, sentencias in migraciones:
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_ID})
            if conn.execute(text("SELECT 1 FROM schema_migrations WHERE id = :i"), {"i": mid}).first():
                continue
            for sql in sentencias:
                conn.execute(text(sql))
            conn.execute(text("INSERT INTO schema_migrations (id) VALUES (:i)"), {"i": mid})
            aplicadas.append(mid)
            log.info("migración aplicada: %s", mid)
    return aplicadas
