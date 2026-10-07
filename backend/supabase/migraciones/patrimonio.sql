-- Módulo Patrimonio e inversiones. Idempotente: se puede ejecutar varias veces.
-- NO ejecutado: correr en Supabase -> SQL Editor (producción) solo con aprobación.
-- (El backend también crea estas tablas al arrancar con create_all; este script
-- existe para dejarlas listas con RLS activado desde el primer momento.)

CREATE TABLE IF NOT EXISTS activos_patrimonio (
    id                 VARCHAR PRIMARY KEY,
    usuario_id         VARCHAR NOT NULL,
    clase              VARCHAR NOT NULL,           -- cdt | fondo | etf | accion | cripto | inmueble | vehiculo
    nombre             VARCHAR NOT NULL,
    moneda             VARCHAR DEFAULT 'COP',
    capital            DOUBLE PRECISION,
    tasa_ea            DOUBLE PRECISION,           -- en %, 12.5 = 12,5 % E.A.
    fecha_inicio       TIMESTAMP,
    fecha_vencimiento  TIMESTAMP,
    ticker             VARCHAR,
    unidades           DOUBLE PRECISION,
    costo_promedio     DOUBLE PRECISION,
    precio_actual      DOUBLE PRECISION,
    precio_fecha       TIMESTAMP,
    fuente_precio      VARCHAR DEFAULT 'manual',
    costo_adquisicion  DOUBLE PRECISION,
    fecha_adquisicion  TIMESTAMP,
    notas              VARCHAR DEFAULT '',
    activo             BOOLEAN DEFAULT TRUE,
    creado_en          TIMESTAMP DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_activos_patrimonio_usuario_id ON activos_patrimonio (usuario_id);

CREATE TABLE IF NOT EXISTS valores_activo (
    id          VARCHAR PRIMARY KEY,
    usuario_id  VARCHAR NOT NULL,
    activo_id   VARCHAR NOT NULL,
    fecha       TIMESTAMP NOT NULL,
    valor       DOUBLE PRECISION NOT NULL,
    fuente      VARCHAR DEFAULT 'manual'
);
CREATE INDEX IF NOT EXISTS ix_valores_activo_usuario_id ON valores_activo (usuario_id);
CREATE INDEX IF NOT EXISTS ix_valores_activo_activo_id ON valores_activo (activo_id);

CREATE TABLE IF NOT EXISTS flujos_activo (
    id          VARCHAR PRIMARY KEY,
    usuario_id  VARCHAR NOT NULL,
    activo_id   VARCHAR NOT NULL,
    fecha       TIMESTAMP NOT NULL,
    monto       DOUBLE PRECISION NOT NULL,         -- <0 aporte, >0 retiro / dividendo
    nota        VARCHAR DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_flujos_activo_usuario_id ON flujos_activo (usuario_id);
CREATE INDEX IF NOT EXISTS ix_flujos_activo_activo_id ON flujos_activo (activo_id);

CREATE TABLE IF NOT EXISTS snapshots_patrimonio (
    id               VARCHAR PRIMARY KEY,
    usuario_id       VARCHAR NOT NULL,
    mes              VARCHAR NOT NULL,             -- 'YYYY-MM'
    fecha            TIMESTAMP DEFAULT (now() AT TIME ZONE 'utc'),
    total_activos    DOUBLE PRECISION DEFAULT 0,
    total_cuentas    DOUBLE PRECISION DEFAULT 0,
    total_deudas     DOUBLE PRECISION DEFAULT 0,
    patrimonio_neto  DOUBLE PRECISION DEFAULT 0,
    distribucion     VARCHAR DEFAULT '{}',
    CONSTRAINT uq_snapshot_usuario_mes UNIQUE (usuario_id, mes)
);
CREATE INDEX IF NOT EXISTS ix_snapshots_patrimonio_usuario_id ON snapshots_patrimonio (usuario_id);

-- RLS: sin políticas, la API REST pública de Supabase (clave anon) no ve nada.
-- El backend se conecta con el rol dueño de las tablas y no se ve afectado.
ALTER TABLE activos_patrimonio   ENABLE ROW LEVEL SECURITY;
ALTER TABLE valores_activo       ENABLE ROW LEVEL SECURITY;
ALTER TABLE flujos_activo        ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots_patrimonio ENABLE ROW LEVEL SECURITY;
