-- Importar mi respaldo + push semanal sin montos. Idempotente. NO se ha ejecutado: main.py
-- crea la tabla (create_all) y la columna al arrancar; esto es solo por si prefieres correrlo a mano.
ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS ocultar_montos BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS importaciones_respaldo (
    id          VARCHAR PRIMARY KEY,
    usuario_id  VARCHAR NOT NULL,
    creado_en   TIMESTAMP,
    deshecho_en TIMESTAMP,
    resumen     VARCHAR DEFAULT '{}',
    lote        VARCHAR DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_importaciones_respaldo_usuario_id ON importaciones_respaldo (usuario_id);
-- Si en tu proyecto Supabase activas RLS, aplícala como en las demás tablas con usuario_id (ver app/rls.py).
