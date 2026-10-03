-- Impuestos (4x1000 y deducibles) + Cierre de mes. Idempotente: se puede ejecutar varias veces.
-- NO ejecutado: correr en Supabase -> SQL Editor (producción) solo con aprobación.
-- (El backend también crea estas tablas al arrancar con create_all; este script existe
-- para dejarlas listas con RLS activado desde el primer momento.)
-- La importación de CSV/Excel no necesita cambios de esquema.

CREATE TABLE IF NOT EXISTS ajustes_usuario (
    usuario_id            VARCHAR PRIMARY KEY,
    cuenta_exenta_gmf_id  VARCHAR,                 -- una cuenta exenta del 4x1000 por titular
    cierre_correo         BOOLEAN DEFAULT FALSE,   -- opt-in: cierre de mes también por correo
    email_cierre          VARCHAR,
    actualizado_en        TIMESTAMP DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS marcas_fiscales (
    id                VARCHAR PRIMARY KEY,
    usuario_id        VARCHAR NOT NULL,
    movimiento_id     VARCHAR NOT NULL,
    categoria_fiscal  VARCHAR NOT NULL,            -- salud | educacion | vivienda_intereses | ahorro_voluntario | donaciones | gmf | otro
    soporte           VARCHAR DEFAULT '',          -- nota/etiqueta de soporte (solo texto)
    estado            VARCHAR DEFAULT 'confirmada',-- confirmada | descartada
    creado_en         TIMESTAMP DEFAULT (now() AT TIME ZONE 'utc'),
    CONSTRAINT uq_marca_fiscal_usuario_mov UNIQUE (usuario_id, movimiento_id)
);
CREATE INDEX IF NOT EXISTS ix_marcas_fiscales_usuario_id ON marcas_fiscales (usuario_id);
CREATE INDEX IF NOT EXISTS ix_marcas_fiscales_movimiento_id ON marcas_fiscales (movimiento_id);

CREATE TABLE IF NOT EXISTS cierres_mes (
    id                 VARCHAR PRIMARY KEY,
    usuario_id         VARCHAR NOT NULL,
    mes                VARCHAR NOT NULL,           -- 'YYYY-MM'
    datos              VARCHAR DEFAULT '{}',       -- JSON del informe
    notificado_push    BOOLEAN DEFAULT FALSE,
    notificado_correo  BOOLEAN DEFAULT FALSE,
    visto              BOOLEAN DEFAULT FALSE,
    creado_en          TIMESTAMP DEFAULT (now() AT TIME ZONE 'utc'),
    CONSTRAINT uq_cierre_usuario_mes UNIQUE (usuario_id, mes)
);
CREATE INDEX IF NOT EXISTS ix_cierres_mes_usuario_id ON cierres_mes (usuario_id);

-- RLS: sin políticas, la API REST pública de Supabase (clave anon) no ve nada.
-- El backend se conecta con el rol dueño de las tablas y no se ve afectado.
ALTER TABLE ajustes_usuario ENABLE ROW LEVEL SECURITY;
ALTER TABLE marcas_fiscales ENABLE ROW LEVEL SECURITY;
ALTER TABLE cierres_mes     ENABLE ROW LEVEL SECURITY;
