-- «Tu plata trabajando»: cajitas/bolsillos y tasas de referencia. Idempotente.
-- NO ejecutado: correr en Supabase -> SQL Editor (producción) solo con aprobación.
-- (El backend también crea estas tablas al arrancar con create_all; este script las deja con RLS desde el primer momento.
--  No hay columnas nuevas en tablas existentes.)

CREATE TABLE IF NOT EXISTS cajitas (
    id          VARCHAR PRIMARY KEY,
    usuario_id  VARCHAR NOT NULL,
    cuenta_id   VARCHAR NOT NULL,
    nombre      VARCHAR NOT NULL,
    saldo       DOUBLE PRECISION DEFAULT 0,   -- parte del saldo de la cuenta apartada aquí (NO es plata adicional)
    tasa_ea     DOUBLE PRECISION,             -- % E.A. propia, opcional
    tasa_fecha  DATE,
    activa      BOOLEAN DEFAULT TRUE,
    creado_en   TIMESTAMP DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_cajitas_usuario_id ON cajitas (usuario_id);
CREATE INDEX IF NOT EXISTS ix_cajitas_cuenta_id ON cajitas (cuenta_id);
CREATE INDEX IF NOT EXISTS ix_cajitas_usuario_cuenta ON cajitas (usuario_id, cuenta_id);

CREATE TABLE IF NOT EXISTS tasas_referencia (
    id             VARCHAR PRIMARY KEY,
    entidad        VARCHAR NOT NULL,
    producto       VARCHAR NOT NULL,
    tipo           VARCHAR NOT NULL DEFAULT 'ahorro_vista',  -- ahorro_vista | saldo_principal | cdt
    tasa_ea        DOUBLE PRECISION,                         -- % E.A.; NULL = sin cifra verificada
    vigente_desde  DATE NOT NULL DEFAULT CURRENT_DATE,
    fuente_url     VARCHAR,
    nota           VARCHAR,
    activa         BOOLEAN DEFAULT TRUE
);

ALTER TABLE cajitas ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasas_referencia ENABLE ROW LEVEL SECURITY;
